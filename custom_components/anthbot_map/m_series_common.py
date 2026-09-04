"""Shared low-level transport for ANTHBOT M-series mower families.

Only behavior that is genuinely shared belongs here. Model-specific policy
(path accumulation, map archive candidates, etc.) is registered by each type
module (m5.py, m9.py, m9_pro.py) through family hooks.
"""

from __future__ import annotations

import base64
import json
import logging
import math
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from . import mqtt_live
from .api import AnthbotGenieApiError, AnthbotShadowApiClient, decode_device_definition
from .base import model_family_key
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .definition_refresh import map_archive_diagnostics, select_map_archive

_LOGGER = logging.getLogger(__name__)

_M_SERIES_SERIALS: set[str] = set()
_INSTALLED = False
_M_SERIES_MAP_PROBE_RETRY_SECONDS = 60.0
_M_SERIES_PATH_MAX_POINTS = 5000
_DEFAULT_MAP_CANDIDATES = ("multi_maps.tar.gz", "map_manager.tar.gz")

PathAccumulator = Callable[[Any, dict[str, Any], list[dict[str, float]]], list[dict[str, float]]]
MapCandidates = Callable[[dict[str, Any]], tuple[str, ...]]

_FAMILY_HOOKS: dict[str, dict[str, Any]] = {}


def register_family(
    family: str,
    *,
    path_accumulator: PathAccumulator | None = None,
    map_candidates: MapCandidates | None = None,
) -> None:
    """Register one explicit mower family with optional family-specific policy."""
    _FAMILY_HOOKS[family] = {
        "path_accumulator": path_accumulator,
        "map_candidates": map_candidates,
    }


def _model_family(model: object) -> str:
    return model_family_key(model)


def _is_registered_family(model: object) -> bool:
    return _model_family(model) in _FAMILY_HOOKS


def _serial_from_topic(topic: str) -> str | None:
    marker = "$aws/things/"
    if not topic.startswith(marker):
        return None
    remainder = topic[len(marker):]
    serial, separator, _ = remainder.partition("/")
    return serial if separator and serial else None


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


def display_path_points(points: Any) -> list[dict[str, float]]:
    """Convert decoded path points to the map-card x/y structure."""
    if not isinstance(points, list):
        return []
    result: list[dict[str, float]] = []
    for point in points:
        if isinstance(point, dict):
            x, y = point.get("x"), point.get("y")
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            x, y = point[0], point[1]
        else:
            continue
        try:
            result.append({"x": float(x), "y": float(y)})
        except (TypeError, ValueError):
            continue
    return result


def valid_pose(value: Any) -> dict[str, Any] | None:
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


def _pose_for_update(reported_pose: Any, fallback_pose: Any) -> dict[str, Any] | None:
    return valid_pose(reported_pose) or valid_pose(fallback_pose)


def point_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    try:
        return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))
    except (KeyError, TypeError, ValueError):
        return float("inf")


def normalize_reported(
    reported: dict[str, Any], fallback_pose: Any = None
) -> dict[str, Any]:
    """Normalize fields common to verified M-series shadow payloads."""
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
            ("volume", "volume"),
            ("anti_loss_radius", "anti_loss_radius"),
            ("anti_loss_switch", "anti_loss_switch"),
            ("camera_switch", "camera_switch"),
            ("indoor_switch", "indoor_switch"),
            ("log_switch", "log_switch"),
            ("pin_code", "pin_code"),
            ("rain_continue_time", "rain_continue_time"),
            ("rain_switch", "rain_switch"),
            ("pobctl_level", "pobctl_level"),
            ("pobctl_switch", "pobctl_switch"),
        ):
            normalized.setdefault(target, device_config.get(source))
        normalized.setdefault(
            "pobctl",
            {
                "level": device_config.get("pobctl_level"),
                "switch": device_config.get("pobctl_switch"),
            },
        )

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
            normalized.setdefault(
                "pose",
                {"x": pose2d.get("x"), "y": pose2d.get("y"), "yaw": pose2d.get("yaw")},
            )
            normalized.setdefault("cur_pose", normalized["pose"])

    pose = _pose_for_update(normalized.get("pose"), fallback_pose)
    if pose is not None:
        normalized["pose"] = pose
        if valid_pose(normalized.get("cur_pose")) is None:
            normalized["cur_pose"] = pose

    curpath = reported.get("curpath")
    decoded_curpath = _decode_live_curpath(curpath)
    if decoded_curpath is not None:
        path_points = display_path_points(decoded_curpath.get("_path_points"))
        if path_points:
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
        else:
            normalized["_path_definition_error"] = "M-series curpath decoded but contained no usable points"

    mode = reported.get("mode")
    if "robot_sta" not in normalized and isinstance(mode, dict) and mode.get("value") is not None:
        normalized["robot_sta"] = {"value": mode.get("value")}
    return normalized


def default_path_accumulator(
    coordinator: Any,
    decoded: dict[str, Any],
    packet_points: list[dict[str, float]],
) -> list[dict[str, float]]:
    """Default M-series append-last-point policy retained from beta3."""
    path_id = decoded.get("path_id")
    accumulator = getattr(coordinator, "_m_series_path_accumulator", [])
    previous_path_id = getattr(coordinator, "_m_series_path_id", None)
    if not isinstance(accumulator, list) or previous_path_id != path_id:
        accumulator = list(packet_points)
        setattr(coordinator, "_m_series_path_id", path_id)
    elif packet_points:
        if not accumulator:
            accumulator = list(packet_points)
        elif point_distance(accumulator[-1], packet_points[-1]) > 0:
            accumulator.append(packet_points[-1])
    return accumulator[-_M_SERIES_PATH_MAX_POINTS:]


def default_map_candidates(property_state: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[str] = []
    map_data = property_state.get("map")
    if isinstance(map_data, dict):
        map_id = map_data.get("map_id")
        if isinstance(map_id, str) and map_id:
            candidates.append(f"map_manager_{map_id}.tar.gz")
    candidates.extend(_DEFAULT_MAP_CANDIDATES)
    return tuple(dict.fromkeys(candidates))


def _family_hook(family: str, name: str, default: Any) -> Any:
    value = _FAMILY_HOOKS.get(family, {}).get(name)
    return value if callable(value) else default


def install_m_series_compat() -> None:
    """Install shared transport wrappers once; type policy remains hook-driven."""
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
        family = _model_family(model)
        setattr(self, "_anthbot_model_family", family)
        if family in _FAMILY_HOOKS:
            _M_SERIES_SERIALS.add(self.client.serial_number)
            setattr(self, "_m_series_path_accumulator", [])
            setattr(self, "_m_series_path_id", None)
            setattr(self, "_m_series_last_pose", None)

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        origin_shadow_name = shadow_name
        family = _model_family(getattr(self.device, "model", None))
        if family in _FAMILY_HOOKS and isinstance(reported, dict):
            fallback_pose = getattr(self, "_m_series_last_pose", None)
            if valid_pose(fallback_pose) is None:
                fallback_pose = self.reported_state.get("pose")
            reported = normalize_reported(reported, fallback_pose=fallback_pose)

            raw_anti_loss = reported.get("anti_loss_pose")
            raw_pose2d = raw_anti_loss.get("pose2d") if isinstance(raw_anti_loss, dict) else None
            has_live_fields = (
                reported.get("_m_series_curpath_definition") is not None
                or valid_pose(raw_pose2d) is not None
            )

            if origin_shadow_name == "service" and has_live_fields:
                _LOGGER.warning(
                    "ANTHBOT %s: live position/path fields found on SERVICE shadow for serial=%s",
                    family,
                    self.client.serial_number,
                )

            if origin_shadow_name == "property" or has_live_fields:
                shadow_name = "property"
                current_pose = valid_pose(reported.get("pose"))
                if current_pose is not None:
                    setattr(self, "_m_series_last_pose", current_pose)

                decoded = reported.get("_m_series_curpath_definition")
                if isinstance(decoded, dict):
                    packet_points = display_path_points(decoded.get("_path_points"))
                    accumulator_fn = _family_hook(
                        family, "path_accumulator", default_path_accumulator
                    )
                    accumulator = accumulator_fn(self, decoded, packet_points)
                    setattr(self, "_m_series_path_accumulator", accumulator)

                    decoded = dict(decoded)
                    decoded["_path_points"] = accumulator
                    decoded["point_count"] = len(accumulator)
                    reported["_m_series_curpath_definition"] = decoded
                    reported["_path_definition"] = decoded
                    reported["path"] = accumulator
                    reported["mowed_path"] = accumulator
                    reported["cloud_path"] = accumulator

        await original_live_shadow(self, shadow_name, reported)

    async def service_state(self) -> dict[str, Any]:
        family = _model_family(getattr(self, "_device_model", None))
        if family in _FAMILY_HOOKS:
            return normalize_reported(
                await self._async_get_named_shadow_reported_state("property")
            )
        return await original_service_state(self)

    async def publish_service_command(self, *, cmd: str, data: Any = None) -> None:
        family = _model_family(getattr(self, "_device_model", None))
        if family not in _FAMILY_HOOKS:
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
            (encoded, True, None, True),
            (encoded, True, encoded, True),
            (encoded, True, None, False),
            (encoded, False, None, True),
            (raw, True, None, True),
            (raw, True, raw, True),
            (raw, False, None, True),
        )
        last_status = 0
        last_body = ""
        last_headers: dict[str, str] = {}
        for refresh_attempt in range(2):
            for request_uri, include_sdk_headers, canonical_uri_override, sign_content_length in attempts:
                status, body_text, response_payload, response_headers = await self._async_signed_post(
                    request_uri=request_uri,
                    canonical_query="",
                    payload_bytes=payload,
                    include_sdk_headers=include_sdk_headers,
                    canonical_uri_override=canonical_uri_override,
                    sign_content_length=sign_content_length,
                )
                last_status, last_body, last_headers = status, body_text, response_headers
                if status == 200 and isinstance(response_payload, dict):
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
            f"{family} command '{cmd}' failed ({last_status}); "
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
        family = _model_family(getattr(self.device, "model", None))
        if family not in _FAMILY_HOOKS:
            return await original_refresh_map(self, property_state, now, allow_periodic=allow_periodic)

        last_probe = float(getattr(self, "_m_series_map_probe_last", 0.0) or 0.0)
        already = str(getattr(self, "_map_definition_source", "")).startswith("m_series_probe:")
        should_probe = not already and (
            last_probe == 0.0 or now - last_probe >= _M_SERIES_MAP_PROBE_RETRY_SECONDS
        )
        if should_probe:
            setattr(self, "_m_series_map_probe_last", now)
            errors: list[str] = []
            candidates_fn = _family_hook(family, "map_candidates", default_map_candidates)
            candidates = candidates_fn(property_state)
            for filename in candidates:
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
                diagnostics.update(
                    {
                        "model_family": family,
                        "preferred_source": "m_series_archive_probe",
                        "active_source": self._map_definition_source,
                        "probe_file": filename,
                        "probe_candidates": list(candidates),
                    }
                )
                return diagnostics, True
            if errors:
                self._map_definition_error = f"{family} archive probe failed: " + " | ".join(errors)

        return await original_refresh_map(self, property_state, now, allow_periodic=allow_periodic)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition
    AnthbotShadowApiClient.async_get_service_reported_state = service_state
    AnthbotShadowApiClient.async_publish_service_command = publish_service_command
    mqtt_live._publish_packet = publish_packet
