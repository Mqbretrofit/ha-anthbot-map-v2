"""Compatibility helpers for ANTHBOT M5/M9 cloud/shadow behavior.

M5/M9 can expose readable REST state via the property named shadow while still
publishing useful live status fragments on the service shadow MQTT topics.
Commands remain writable through the service named shadow.
"""

from __future__ import annotations

import base64
import json
import logging
import math
from typing import Any
from urllib.parse import quote

from . import mqtt_live
from .api import AnthbotGenieApiError, AnthbotShadowApiClient, decode_device_definition
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .definition_refresh import map_archive_diagnostics, select_map_archive

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("ANTHBOT TEST: m_series_compat.py loaded")

_M_SERIES_SERIALS: set[str] = set()
_INSTALLED = False
_M_SERIES_MAP_PROBE_RETRY_SECONDS = 60.0
_M_SERIES_PATH_SCALE = 1000.0
_M_SERIES_PATH_MAX_POINTS = 5000
_M_SERIES_MAP_CANDIDATES = ("multi_maps.tar.gz", "map_manager.tar.gz")

_SENSITIVE_FIELD_PARTS = (
    "ssid", "bssid", "password", "passwd", "token", "secret", "access_key",
    "session_key", "pin", "ccid", "iccid", "imei", "imsi", "latitude",
    "longitude", "gps_lat", "gps_lon", "ip", "mac",
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
    if _is_sensitive_key(key):
        return "<redacted>"
    if depth >= 3:
        return "<nested>"
    if isinstance(value, dict):
        return {
            str(k): _sanitize_shadow_value(k, v, depth=depth + 1)
            for k, v in list(value.items())[:30]
        }
    if isinstance(value, list):
        return [_sanitize_shadow_value(key, item, depth=depth + 1) for item in value[:15]]
    if isinstance(value, str) and len(value) > 120:
        return value[:117] + "..."
    return value


def _shadow_diagnostic_payload(reported: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): _sanitize_shadow_value(key, value)
        for key, value in list(reported.items())[:120]
    }


def _decode_live_curpath(value: Any) -> dict[str, Any] | None:
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


def _m_series_display_path_points(points: Any) -> list[dict[str, float]]:
    if not isinstance(points, list):
        return []
    display_points: list[dict[str, float]] = []
    for point in points:
        if isinstance(point, dict):
            x, y = point.get("x"), point.get("y")
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            x, y = point[0], point[1]
        else:
            continue
        try:
            display_points.append({"x": float(x), "y": float(y)})
        except (TypeError, ValueError):
            continue
    return display_points


def _m_series_valid_pose(value: Any) -> dict[str, Any] | None:
    """Return a finite M-series pose or None when the delta omitted it."""
    if not isinstance(value, dict):
        return None
    try:
        x = float(value.get("x"))
        y = float(value.get("y"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    pose = dict(value)
    pose["x"] = x
    pose["y"] = y
    return pose


def _m_series_pose_for_update(
    reported_pose: Any, fallback_pose: Any
) -> tuple[dict[str, Any] | None, str]:
    """Select the live pose, retaining the previous one for curpath deltas."""
    pose = _m_series_valid_pose(reported_pose)
    if pose is not None:
        return pose, "reported"
    pose = _m_series_valid_pose(fallback_pose)
    if pose is not None:
        return pose, "cached"
    return None, "missing"


def _m_series_anchor_path_to_pose(points: Any, pose: Any) -> list[dict[str, float]]:
    """Convert M-series millimetre path coordinates to live world coordinates.

    The M5/M9 curpath uses a map-local integer coordinate system while the live
    pose exposed by the property shadow is in metres. The last curpath point is
    the mower's current location, so use it as the origin anchor and convert
    packet deltas from millimetres to metres.
    """
    raw = _m_series_display_path_points(points)
    if not raw:
        return []
    valid_pose = _m_series_valid_pose(pose)
    if valid_pose is None:
        return []
    pose_x = float(valid_pose["x"])
    pose_y = float(valid_pose["y"])
    anchor = raw[-1]
    return [
        {
            "x": pose_x + (point["x"] - anchor["x"]) / _M_SERIES_PATH_SCALE,
            "y": pose_y + (point["y"] - anchor["y"]) / _M_SERIES_PATH_SCALE,
        }
        for point in raw
    ]


def _point_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    try:
        return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))
    except (KeyError, TypeError, ValueError):
        return float("inf")


def _path_coordinate_diagnostics(points: Any, pose: Any) -> dict[str, Any] | None:
    display = _m_series_display_path_points(points)
    if not display:
        return None
    xs = [point["x"] for point in display]
    ys = [point["y"] for point in display]
    result: dict[str, Any] = {
        "count": len(display),
        "first": display[0],
        "last": display[-1],
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
        "span_x": max(xs) - min(xs),
        "span_y": max(ys) - min(ys),
    }
    if isinstance(pose, dict):
        try:
            px, py = float(pose.get("x")), float(pose.get("y"))
            result["pose"] = {"x": px, "y": py}
            result["first_minus_pose"] = {"x": display[0]["x"] - px, "y": display[0]["y"] - py}
            result["last_minus_pose"] = {"x": display[-1]["x"] - px, "y": display[-1]["y"] - py}
        except (TypeError, ValueError):
            pass
    return result


def _normalize_m_series_reported(
    reported: dict[str, Any], fallback_pose: Any = None
) -> dict[str, Any]:
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
        for target, source in (
            ("volume", "volume"), ("anti_loss_radius", "anti_loss_radius"),
            ("anti_loss_switch", "anti_loss_switch"), ("camera_switch", "camera_switch"),
            ("indoor_switch", "indoor_switch"), ("log_switch", "log_switch"),
            ("pin_code", "pin_code"), ("rain_continue_time", "rain_continue_time"),
            ("rain_switch", "rain_switch"), ("pobctl_level", "pobctl_level"),
            ("pobctl_switch", "pobctl_switch"),
        ):
            normalized.setdefault(target, device_config.get(source))
        normalized.setdefault("pobctl", {
            "level": device_config.get("pobctl_level"),
            "switch": device_config.get("pobctl_switch"),
        })

    for key, target in (("mowing_time", "mowing_time_new"), ("mowing_area", "mowing_area_new")):
        value = reported.get(key)
        if isinstance(value, dict):
            normalized.setdefault(target, value)

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
        normalized["ota_status"].setdefault("ota_progress", ota_status.get("progress"))
        normalized["ota_status"].setdefault("ota_state", ota_status.get("states"))

    anti_loss_pose = reported.get("anti_loss_pose")
    if isinstance(anti_loss_pose, dict):
        pose2d = anti_loss_pose.get("pose2d")
        if isinstance(pose2d, dict):
            normalized.setdefault("pose", {
                "x": pose2d.get("x"), "y": pose2d.get("y"), "yaw": pose2d.get("yaw")
            })
            normalized.setdefault("cur_pose", normalized["pose"])

    pose, pose_source = _m_series_pose_for_update(
        normalized.get("pose"), fallback_pose
    )
    normalized["_m_series_pose_source"] = pose_source
    if pose is not None:
        normalized["pose"] = pose
        if _m_series_valid_pose(normalized.get("cur_pose")) is None:
            normalized["cur_pose"] = pose

    curpath = reported.get("curpath")
    decoded_curpath = _decode_live_curpath(curpath)
    if decoded_curpath is not None:
        raw_path_points = decoded_curpath.get("_path_points")
        path_points = _m_series_anchor_path_to_pose(raw_path_points, normalized.get("pose"))
        normalized["_m_series_curpath_coords_raw"] = _path_coordinate_diagnostics(
            raw_path_points, normalized.get("pose")
        )
        if path_points:
            decoded_curpath = dict(decoded_curpath)
            decoded_curpath["source_coordinate_scale"] = decoded_curpath.get(
                "coordinate_scale"
            )
            decoded_curpath["_path_points_raw"] = raw_path_points
            decoded_curpath["_path_points"] = path_points
            decoded_curpath["coordinate_scale"] = 1
            normalized["path"] = path_points
            normalized["mowed_path"] = path_points
            normalized["cloud_path"] = path_points
            normalized["_m_series_curpath_coords"] = _path_coordinate_diagnostics(path_points, normalized.get("pose"))
            normalized["_m_series_curpath_definition"] = decoded_curpath
            normalized["_path_definition"] = decoded_curpath
            normalized["_path_definition_error"] = None
            normalized["_history_path_source"] = "m_series_curpath"
            normalized["_history_path_live_refresh"] = True
            if isinstance(curpath, dict) and curpath.get("time") is not None:
                normalized.setdefault("path_time", curpath.get("time"))
        else:
            normalized["_path_definition_error"] = (
                "M-series curpath is waiting for the first valid live pose"
            )

    mode = reported.get("mode")
    if "robot_sta" not in normalized and isinstance(mode, dict) and mode.get("value") is not None:
        normalized["robot_sta"] = {"value": mode.get("value")}
    return normalized


def _m_series_map_candidates(property_state: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[str] = []
    map_data = property_state.get("map")
    if isinstance(map_data, dict):
        map_id = map_data.get("map_id")
        if isinstance(map_id, str) and map_id:
            candidates.append(f"map_manager_{map_id}.tar.gz")
    candidates.extend(_M_SERIES_MAP_CANDIDATES)
    return tuple(dict.fromkeys(candidates))


def install_m_series_compat() -> None:
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
            self.client.serial_number, model, is_m_series,
        )
        if is_m_series:
            _M_SERIES_SERIALS.add(self.client.serial_number)
            setattr(self, "_m_series_shadow_diag_signatures", {})
            setattr(self, "_m_series_path_accumulator", [])
            setattr(self, "_m_series_path_id", None)
            setattr(self, "_m_series_last_pose", None)

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        if _is_m_series(getattr(self.device, "model", None)) and isinstance(reported, dict):
            safe_payload = _shadow_diagnostic_payload(reported)
            signature = json.dumps(safe_payload, sort_keys=True, separators=(",", ":"), default=str)
            signatures = getattr(self, "_m_series_shadow_diag_signatures", None)
            if not isinstance(signatures, dict):
                signatures = {}
                setattr(self, "_m_series_shadow_diag_signatures", signatures)
            if signatures.get(shadow_name) != signature:
                signatures[shadow_name] = signature
                _LOGGER.warning(
                    "ANTHBOT M-SERIES SHADOW: serial=%s shadow=%s fields=%s",
                    self.client.serial_number, shadow_name, signature,
                )

            fallback_pose = getattr(self, "_m_series_last_pose", None)
            if _m_series_valid_pose(fallback_pose) is None:
                fallback_pose = self.reported_state.get("pose")
            reported = _normalize_m_series_reported(
                reported, fallback_pose=fallback_pose
            )
            current_pose = _m_series_valid_pose(reported.get("pose"))
            if current_pose is not None:
                setattr(self, "_m_series_last_pose", current_pose)
            decoded = reported.get("_m_series_curpath_definition")
            if isinstance(decoded, dict):
                packet_points = _m_series_display_path_points(decoded.get("_path_points"))
                path_id = decoded.get("path_id")
                accumulator = getattr(self, "_m_series_path_accumulator", [])
                previous_path_id = getattr(self, "_m_series_path_id", None)
                if not isinstance(accumulator, list) or previous_path_id != path_id:
                    accumulator = list(packet_points)
                    setattr(self, "_m_series_path_id", path_id)
                elif packet_points:
                    if not accumulator:
                        accumulator = list(packet_points)
                    else:
                        current = packet_points[-1]
                        distance = _point_distance(accumulator[-1], current)
                        if 0.02 <= distance <= 5.0:
                            accumulator.append(current)
                        elif distance > 5.0:
                            _LOGGER.warning(
                                "ANTHBOT M-SERIES CURPATH JUMP: serial=%s distance=%.3fm; restarting trail",
                                self.client.serial_number, distance,
                            )
                            accumulator = list(packet_points)
                accumulator = accumulator[-_M_SERIES_PATH_MAX_POINTS:]
                setattr(self, "_m_series_path_accumulator", accumulator)

                decoded = dict(decoded)
                decoded["_path_points"] = accumulator
                decoded["point_count"] = len(accumulator)
                decoded["coordinate_scale"] = 1
                reported["_m_series_curpath_definition"] = decoded
                reported["_path_definition"] = decoded
                reported["path"] = accumulator
                reported["mowed_path"] = accumulator
                reported["cloud_path"] = accumulator

                _LOGGER.warning(
                    "ANTHBOT M-SERIES CURPATH: serial=%s format=%s packet_points=%s accumulated=%s path_id=%s scale=1/%s anchored_to_pose=true",
                    self.client.serial_number, decoded.get("format"), len(packet_points),
                    len(accumulator), path_id, int(_M_SERIES_PATH_SCALE),
                )
                raw_coords = reported.get("_m_series_curpath_coords_raw")
                anchored_coords = reported.get("_m_series_curpath_coords")
                accumulated_coords = _path_coordinate_diagnostics(
                    accumulator, reported.get("pose")
                )
                if any(
                    isinstance(value, dict)
                    for value in (raw_coords, anchored_coords, accumulated_coords)
                ):
                    coordinate_diagnostics = {
                        "path_id": path_id,
                        "format": decoded.get("format"),
                        "source_coordinate_scale": decoded.get(
                            "source_coordinate_scale"
                        ),
                        "assumed_raw_units_per_pose_unit": _M_SERIES_PATH_SCALE,
                        "pose": reported.get("pose"),
                        "pose_source": reported.get("_m_series_pose_source"),
                        "raw": raw_coords,
                        "anchored_packet": anchored_coords,
                        "accumulated": accumulated_coords,
                    }
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES CURPATH COORDS: serial=%s coords=%s",
                        self.client.serial_number,
                        json.dumps(
                            coordinate_diagnostics,
                            separators=(",", ":"),
                            sort_keys=True,
                            default=str,
                        ),
                    )
        await original_live_shadow(self, shadow_name, reported)

    async def service_state(self) -> dict[str, Any]:
        if _is_m_series(getattr(self, "_device_model", None)):
            return _normalize_m_series_reported(
                await self._async_get_named_shadow_reported_state("property")
            )
        return await original_service_state(self)

    async def publish_service_command(self, *, cmd: str, data: Any = None) -> None:
        if not _is_m_series(getattr(self, "_device_model", None)):
            await original_publish(self, cmd=cmd, data=data)
            return
        if cmd == "param_set":
            value = data
            if isinstance(data, dict):
                value = next(
                    (data[key] for key in ("mow_head", "value", "cutter_ctl_cutter_lift", "cutter_height") if key in data),
                    next(iter(data.values()), None),
                )
            desired_data: Any = {"cutter_ctl_cutter_lift": int(value)} if value is not None else {}
        elif cmd == "volume_ctl":
            value = data
            if isinstance(data, dict):
                value = next(
                    (data[key] for key in ("volume", "volume_ctl", "value") if key in data),
                    next(iter(data.values()), None),
                )
            desired_data = {"volume_ctl": int(value)} if value is not None else {}
        else:
            desired_data = data if isinstance(data, dict) else {cmd: data}

        body = {"state": {"desired": {"cmd": cmd, "data": desired_data}}}
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        topic = f"$aws/things/{self.serial_number}/shadow/name/service/update"
        encoded = "/topics/" + quote(topic, safe="-_.~")
        raw = f"/topics/{topic}"
        attempts = (
            (encoded, True, None, True), (encoded, True, encoded, True),
            (encoded, True, None, False), (encoded, False, None, True),
            (raw, True, None, True), (raw, True, raw, True), (raw, False, None, True),
        )
        last_status = 0
        last_body = ""
        last_headers: dict[str, str] = {}
        for refresh_attempt in range(2):
            for attempt_index, (request_uri, include_sdk_headers, canonical_uri_override, sign_content_length) in enumerate(attempts):
                status, body_text, response_payload, response_headers = await self._async_signed_post(
                    request_uri=request_uri, canonical_query="", payload_bytes=payload,
                    include_sdk_headers=include_sdk_headers,
                    canonical_uri_override=canonical_uri_override,
                    sign_content_length=sign_content_length,
                )
                last_status, last_body, last_headers = status, body_text, response_headers
                if status == 200 and isinstance(response_payload, dict):
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES COMMAND TEST: serial=%s cmd=%s accepted via signed POST attempt=%s refreshed=%s",
                        self.serial_number, cmd, attempt_index + 1, refresh_attempt > 0,
                    )
                    return
                if status != 403:
                    break
            if last_status == 403 and refresh_attempt == 0:
                try:
                    await self._async_get_credentials(force_refresh=True)
                    continue
                except Exception:
                    pass
            break
        publisher = getattr(self, "_live_command_publisher", None)
        if publisher is not None:
            await publisher(topic, payload)
            return
        raise AnthbotGenieApiError(
            f"M-series command '{cmd}' failed ({last_status}); "
            f"errortype={last_headers.get('x-amzn-errortype', '')}; body={last_body[:240]}"
        )

    def publish_packet(topic: str, payload: bytes = b"{}") -> bytes:
        serial = _serial_from_topic(topic)
        if serial in _M_SERIES_SERIALS and topic.endswith("/service/get"):
            topic = topic.replace("/service/get", "/property/get")
        return original_publish_packet(topic, payload)

    async def refresh_map_definition(
        self, property_state: dict[str, Any], now: float, *, allow_periodic: bool
    ) -> tuple[dict[str, Any], bool]:
        model = getattr(self.device, "model", None)
        if not _is_m_series(model):
            return await original_refresh_map(self, property_state, now, allow_periodic=allow_periodic)
        last_probe = float(getattr(self, "_m_series_map_probe_last", 0.0) or 0.0)
        already = str(getattr(self, "_map_definition_source", "")).startswith("m_series_probe:")
        should_probe = not already and (
            last_probe == 0.0 or now - last_probe >= _M_SERIES_MAP_PROBE_RETRY_SECONDS
        )
        if should_probe:
            setattr(self, "_m_series_map_probe_last", now)
            errors: list[str] = []
            candidates = _m_series_map_candidates(property_state)
            for filename in candidates:
                _LOGGER.warning(
                    "ANTHBOT M-SERIES MAP TEST: serial=%s model=%s probing filename=%s sub_category=multi_maps",
                    self.client.serial_number, model, filename,
                )
                try:
                    definition = await self.account_client.async_get_device_map_archive(
                        self.client.serial_number, filename
                    )
                except AnthbotGenieApiError as err:
                    errors.append(f"{filename}: {str(err)[:240]}")
                    continue
                self._map_definition = definition
                self._map_definition_source = f"m_series_probe:{filename}"
                self._map_definition_error = None
                self._last_map_download_monotonic = now
                diagnostics = map_archive_diagnostics(property_state, select_map_archive(property_state))
                diagnostics.update({
                    "preferred_source": "m_series_archive_probe",
                    "active_source": self._map_definition_source,
                    "probe_file": filename,
                    "probe_candidates": list(candidates),
                })
                return diagnostics, True
            if errors:
                self._map_definition_error = "M-series archive probe failed: " + " | ".join(errors)
        return await original_refresh_map(self, property_state, now, allow_periodic=allow_periodic)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition
    AnthbotShadowApiClient.async_get_service_reported_state = service_state
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    mqtt_live._publish_packet = publish_packet
