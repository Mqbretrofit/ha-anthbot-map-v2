"""Compatibility helpers for ANTHBOT M5/M9 cloud/shadow behavior.

M5/M9 can expose readable REST state via the property named shadow while still
publishing useful live status fragments on the service shadow MQTT topics.
Commands remain writable through the service named shadow.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any
from urllib.parse import quote

from . import mqtt_live
from .api import (
    AnthbotGenieApiError,
    AnthbotShadowApiClient,
    decode_device_definition,
)
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .definition_refresh import map_archive_diagnostics, select_map_archive

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("ANTHBOT TEST: m_series_compat.py loaded")

_M_SERIES_SERIALS: set[str] = set()
_INSTALLED = False
_M_SERIES_MAP_PROBE_RETRY_SECONDS = 60.0
_M_SERIES_MAP_CANDIDATES = (
    "multi_maps.tar.gz",
    "map_manager.tar.gz",
)

_SENSITIVE_FIELD_PARTS = (
    "ssid",
    "bssid",
    "password",
    "passwd",
    "token",
    "secret",
    "access_key",
    "session_key",
    "pin",
    "ccid",
    "iccid",
    "imei",
    "imsi",
    "latitude",
    "longitude",
    "gps_lat",
    "gps_lon",
    "ip",
    "mac",
)


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _serial_from_topic(topic: str) -> str | None:
    marker = "$aws/things/"
    if not topic.startswith(marker):
        return None
    remainder = topic[len(marker):]
    serial, separator, _ = remainder.partition("/")
    return serial if separator and serial else None


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key or "").lower()
    return any(part in normalized for part in _SENSITIVE_FIELD_PARTS)


def _sanitize_shadow_value(key: object, value: Any, *, depth: int = 0) -> Any:
    """Return a compact log-safe representation of an M-series shadow value."""
    if _is_sensitive_key(key):
        return "<redacted>"
    if depth >= 3:
        return "<nested>"
    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_shadow_value(
                child_key, child_value, depth=depth + 1
            )
            for child_key, child_value in list(value.items())[:30]
        }
    if isinstance(value, list):
        return [
            _sanitize_shadow_value(key, item, depth=depth + 1)
            for item in value[:15]
        ]
    if isinstance(value, str) and len(value) > 120:
        return value[:117] + "..."
    return value


def _shadow_diagnostic_payload(reported: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): _sanitize_shadow_value(key, value)
        for key, value in list(reported.items())[:120]
    }


def _decode_live_curpath(value: Any) -> dict[str, Any] | None:
    """Decode the M5/M9 base64 curpath using the integration's path decoder."""
    raw_value = value.get("value") if isinstance(value, dict) else value
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        raw_bytes = base64.b64decode(raw_value, validate=True)
    except (ValueError, TypeError):
        return None
    decoded = decode_device_definition(raw_bytes, "m_series_curpath.path")
    if not isinstance(decoded, dict):
        return None
    points = decoded.get("_path_points")
    if not isinstance(points, list) or not points:
        return None
    return decoded


def _normalize_m_series_reported(reported: dict[str, Any]) -> dict[str, Any]:
    """Expose M5/M9 nested fields through the legacy keys used by v2 sensors."""
    normalized = dict(reported)

    online = reported.get("online")
    if isinstance(online, dict) and "value" in online:
        normalized["online"] = online.get("value")
        if "time" in online and "timestamp" not in normalized:
            normalized["timestamp"] = online.get("time")

    net_state = reported.get("net_state")
    if isinstance(net_state, dict):
        normalized.setdefault("wifi_state", net_state.get("wifi_state"))
        normalized.setdefault("4g_state", net_state.get("4g_state"))

    net_config = reported.get("net_config")
    if isinstance(net_config, dict):
        normalized.setdefault("sta_ssid", net_config.get("ssid"))
        normalized.setdefault("sta_ip_addr", net_config.get("ip"))
        normalized.setdefault("4g_ccid", net_config.get("4g_ccid"))

    device_config = reported.get("device_config")
    if isinstance(device_config, dict):
        normalized.setdefault("volume", device_config.get("volume"))
        normalized.setdefault("anti_loss_radius", device_config.get("anti_loss_radius"))
        normalized.setdefault("anti_loss_switch", device_config.get("anti_loss_switch"))
        normalized.setdefault("camera_switch", device_config.get("camera_switch"))
        normalized.setdefault("indoor_switch", device_config.get("indoor_switch"))
        normalized.setdefault("log_switch", device_config.get("log_switch"))
        normalized.setdefault("pin_code", device_config.get("pin_code"))
        normalized.setdefault("rain_continue_time", device_config.get("rain_continue_time"))
        normalized.setdefault("rain_switch", device_config.get("rain_switch"))
        normalized.setdefault("pobctl_level", device_config.get("pobctl_level"))
        normalized.setdefault("pobctl_switch", device_config.get("pobctl_switch"))
        normalized.setdefault(
            "pobctl",
            {
                "level": device_config.get("pobctl_level"),
                "switch": device_config.get("pobctl_switch"),
            },
        )

    mowing_time = reported.get("mowing_time")
    if isinstance(mowing_time, dict):
        normalized.setdefault("mowing_time_new", mowing_time)

    mowing_area = reported.get("mowing_area")
    if isinstance(mowing_area, dict):
        normalized.setdefault("mowing_area_new", mowing_area)

    map_data = reported.get("map")
    if isinstance(map_data, dict):
        normalized.setdefault("map_area", map_data.get("map_area"))
        normalized.setdefault("map_sta", {"value": map_data.get("state")})
        normalized.setdefault("map_time", map_data.get("time"))
        if map_data.get("map_id"):
            normalized.setdefault("has_map", {"value": 1})

    event = reported.get("event")
    if isinstance(event, dict):
        normalized.setdefault("event_code", event.get("value"))

    error = reported.get("error")
    if isinstance(error, dict):
        normalized.setdefault("err_code", error.get("value"))

    rtk = reported.get("rtk")
    if isinstance(rtk, dict):
        normalized.setdefault("rtk_state", rtk.get("state"))
        normalized.setdefault("rtk_move_sta", {"value": rtk.get("moved")})

    ota_status = reported.get("ota_status")
    if isinstance(ota_status, dict):
        normalized.setdefault("ota_status", dict(ota_status))
        if "ota_progress" not in normalized["ota_status"]:
            normalized["ota_status"]["ota_progress"] = ota_status.get("progress")
        if "ota_state" not in normalized["ota_status"]:
            normalized["ota_status"]["ota_state"] = ota_status.get("states")

    anti_loss_pose = reported.get("anti_loss_pose")
    if isinstance(anti_loss_pose, dict):
        pose2d = anti_loss_pose.get("pose2d")
        if isinstance(pose2d, dict):
            normalized.setdefault(
                "pose",
                {
                    "x": pose2d.get("x"),
                    "y": pose2d.get("y"),
                    "yaw": pose2d.get("yaw"),
                },
            )
            normalized.setdefault("cur_pose", normalized["pose"])

    curpath = reported.get("curpath")
    decoded_curpath = _decode_live_curpath(curpath)
    if decoded_curpath is not None:
        path_points = decoded_curpath.get("_path_points")
        if isinstance(path_points, list):
            normalized["path"] = path_points
            normalized["mowed_path"] = path_points
            normalized["cloud_path"] = path_points
        normalized["_m_series_curpath_definition"] = decoded_curpath
        normalized["_path_definition"] = decoded_curpath
        normalized["_path_definition_error"] = None
        normalized["_history_path_source"] = "m_series_curpath"
        normalized["_history_path_live_refresh"] = True
        if isinstance(curpath, dict) and curpath.get("time") is not None:
            normalized.setdefault("path_time", curpath.get("time"))

    mode = reported.get("mode")
    if "robot_sta" not in normalized and isinstance(mode, dict):
        mode_value = mode.get("value")
        if mode_value is not None:
            normalized["robot_sta"] = {"value": mode_value}

    return normalized


def _m_series_map_candidates(property_state: dict[str, Any]) -> tuple[str, ...]:
    """Return app-derived map archive candidates, preferring the active map id."""
    candidates: list[str] = []
    map_data = property_state.get("map")
    if isinstance(map_data, dict):
        map_id = map_data.get("map_id")
        if isinstance(map_id, str) and map_id:
            candidates.append(f"map_manager_{map_id}.tar.gz")
    candidates.extend(_M_SERIES_MAP_CANDIDATES)
    return tuple(dict.fromkeys(candidates))


def install_m_series_compat() -> None:
    """Install model-aware M5/M9 behavior once per Home Assistant process."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_coordinator_init = AnthbotGenieDataUpdateCoordinator.__init__
    original_live_shadow = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    original_service_state = AnthbotShadowApiClient.async_get_service_reported_state
    original_publish = AnthbotShadowApiClient.async_publish_service_command
    original_publish_packet = mqtt_live._publish_packet
    original_refresh_map = AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        original_coordinator_init(self, *args, **kwargs)
        model = getattr(self.device, "model", None)
        setattr(self.client, "_device_model", model)
        is_m_series = _is_m_series(model)
        _LOGGER.warning(
            "ANTHBOT MODEL TEST: serial=%s, model=%s, m_series=%s",
            self.client.serial_number,
            model,
            is_m_series,
        )
        if is_m_series:
            _M_SERIES_SERIALS.add(self.client.serial_number)
            setattr(self, "_m_series_shadow_diag_signatures", {})

    async def live_shadow(
        self,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        if _is_m_series(getattr(self.device, "model", None)) and isinstance(
            reported, dict
        ):
            safe_payload = _shadow_diagnostic_payload(reported)
            signature = json.dumps(
                safe_payload,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            signatures = getattr(self, "_m_series_shadow_diag_signatures", None)
            if not isinstance(signatures, dict):
                signatures = {}
                setattr(self, "_m_series_shadow_diag_signatures", signatures)
            if signatures.get(shadow_name) != signature:
                signatures[shadow_name] = signature
                _LOGGER.warning(
                    "ANTHBOT M-SERIES SHADOW: serial=%s shadow=%s fields=%s",
                    self.client.serial_number,
                    shadow_name,
                    signature,
                )
            reported = _normalize_m_series_reported(reported)
            decoded = reported.get("_m_series_curpath_definition")
            if isinstance(decoded, dict):
                _LOGGER.warning(
                    "ANTHBOT M-SERIES CURPATH: serial=%s format=%s points=%s path_id=%s header_len=%s protocol_version=%s",
                    self.client.serial_number,
                    decoded.get("format"),
                    decoded.get("point_count"),
                    decoded.get("path_id"),
                    decoded.get("header_len"),
                    decoded.get("protocol_version"),
                )
        await original_live_shadow(self, shadow_name, reported)

    async def service_state(self) -> dict[str, Any]:
        if _is_m_series(getattr(self, "_device_model", None)):
            state = await self._async_get_named_shadow_reported_state("property")
            return _normalize_m_series_reported(state)
        return await original_service_state(self)

    async def publish_service_command(self, *, cmd: str, data: Any = None) -> None:
        if not _is_m_series(getattr(self, "_device_model", None)):
            await original_publish(self, cmd=cmd, data=data)
            return

        if cmd == "param_set":
            value = data
            if isinstance(data, dict):
                value = next(
                    (
                        data[key]
                        for key in (
                            "mow_head",
                            "value",
                            "cutter_ctl_cutter_lift",
                            "cutter_height",
                        )
                        if key in data
                    ),
                    next(iter(data.values()), None),
                )
            desired_data: Any = (
                {"cutter_ctl_cutter_lift": int(value)} if value is not None else {}
            )
        elif cmd == "volume_ctl":
            value = data
            if isinstance(data, dict):
                value = next(
                    (
                        data[key]
                        for key in ("volume", "volume_ctl", "value")
                        if key in data
                    ),
                    next(iter(data.values()), None),
                )
            desired_data = {"volume_ctl": int(value)} if value is not None else {}
        else:
            desired_data = data if isinstance(data, dict) else {cmd: data}

        body = {
            "state": {
                "desired": {
                    "cmd": cmd,
                    "data": desired_data,
                }
            }
        }
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        topic = f"$aws/things/{self.serial_number}/shadow/name/service/update"
        request_uri_encoded = "/topics/" + quote(topic, safe="-_.~")
        request_uri_raw = f"/topics/{topic}"

        attempts = (
            (request_uri_encoded, True, None, True),
            (request_uri_encoded, True, request_uri_encoded, True),
            (request_uri_encoded, True, None, False),
            (request_uri_encoded, False, None, True),
            (request_uri_raw, True, None, True),
            (request_uri_raw, True, request_uri_raw, True),
            (request_uri_raw, False, None, True),
        )
        last_status = 0
        last_body = ""
        last_headers: dict[str, str] = {}

        for refresh_attempt in range(2):
            for attempt_index, (
                request_uri,
                include_sdk_headers,
                canonical_uri_override,
                sign_content_length,
            ) in enumerate(attempts):
                status, body_text, response_payload, response_headers = (
                    await self._async_signed_post(
                        request_uri=request_uri,
                        canonical_query="",
                        payload_bytes=payload,
                        include_sdk_headers=include_sdk_headers,
                        canonical_uri_override=canonical_uri_override,
                        sign_content_length=sign_content_length,
                    )
                )
                last_status = status
                last_body = body_text
                last_headers = response_headers
                if status == 200 and isinstance(response_payload, dict):
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES COMMAND TEST: serial=%s cmd=%s accepted via signed POST attempt=%s refreshed=%s",
                        self.serial_number,
                        cmd,
                        attempt_index + 1,
                        refresh_attempt > 0,
                    )
                    return
                if status != 403:
                    break

            if last_status == 403 and refresh_attempt == 0:
                try:
                    await self._async_get_credentials(force_refresh=True)
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES COMMAND TEST: serial=%s cmd=%s got 403; refreshed STS credentials",
                        self.serial_number,
                        cmd,
                    )
                    continue
                except Exception as err:
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES COMMAND TEST: serial=%s cmd=%s STS refresh failed: %s",
                        self.serial_number,
                        cmd,
                        err,
                    )
            break

        publisher = getattr(self, "_live_command_publisher", None)
        if publisher is not None:
            _LOGGER.warning(
                "ANTHBOT M-SERIES COMMAND TEST: serial=%s cmd=%s signed POST failed status=%s errortype=%s; trying MQTT with M-series payload",
                self.serial_number,
                cmd,
                last_status,
                last_headers.get("x-amzn-errortype", ""),
            )
            await publisher(topic, payload)
            return

        raise AnthbotGenieApiError(
            f"M-series command '{cmd}' failed ({last_status}); "
            f"errortype={last_headers.get('x-amzn-errortype', '')}; "
            f"body={last_body[:240]}"
        )

    def publish_packet(topic: str, payload: bytes = b"{}") -> bytes:
        serial = _serial_from_topic(topic)
        if serial in _M_SERIES_SERIALS and topic.endswith("/service/get"):
            topic = topic.replace("/service/get", "/property/get")
        return original_publish_packet(topic, payload)

    async def refresh_map_definition(
        self,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        model = getattr(self.device, "model", None)
        if not _is_m_series(model):
            return await original_refresh_map(
                self,
                property_state,
                now,
                allow_periodic=allow_periodic,
            )

        last_probe = float(getattr(self, "_m_series_map_probe_last", 0.0) or 0.0)
        already_using_probe = str(getattr(self, "_map_definition_source", "")).startswith(
            "m_series_probe:"
        )
        should_probe = (
            not already_using_probe
            and (last_probe == 0.0 or now - last_probe >= _M_SERIES_MAP_PROBE_RETRY_SECONDS)
        )

        if should_probe:
            setattr(self, "_m_series_map_probe_last", now)
            errors: list[str] = []
            candidates = _m_series_map_candidates(property_state)
            for filename in candidates:
                _LOGGER.warning(
                    "ANTHBOT M-SERIES MAP TEST: serial=%s model=%s probing filename=%s sub_category=multi_maps",
                    self.client.serial_number,
                    model,
                    filename,
                )
                try:
                    definition = await self.account_client.async_get_device_map_archive(
                        self.client.serial_number,
                        filename,
                    )
                except AnthbotGenieApiError as err:
                    error_text = str(err).replace("\n", " ")[:240]
                    errors.append(f"{filename}: {error_text}")
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES MAP TEST: serial=%s filename=%s failed: %s",
                        self.client.serial_number,
                        filename,
                        error_text,
                    )
                    continue

                self._map_definition = definition
                self._map_definition_source = f"m_series_probe:{filename}"
                self._map_definition_error = None
                self._last_map_download_monotonic = now
                diagnostics = map_archive_diagnostics(
                    property_state,
                    select_map_archive(property_state),
                )
                diagnostics.update(
                    {
                        "preferred_source": "m_series_archive_probe",
                        "active_source": self._map_definition_source,
                        "probe_file": filename,
                        "probe_candidates": list(candidates),
                    }
                )
                _LOGGER.warning(
                    "ANTHBOT M-SERIES MAP TEST: SUCCESS serial=%s model=%s filename=%s",
                    self.client.serial_number,
                    model,
                    filename,
                )
                return diagnostics, True

            if errors:
                self._map_definition_error = "M-series archive probe failed: " + " | ".join(errors)

        return await original_refresh_map(
            self,
            property_state,
            now,
            allow_periodic=allow_periodic,
        )

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition
    AnthbotShadowApiClient.async_get_service_reported_state = service_state
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    mqtt_live._publish_packet = publish_packet
