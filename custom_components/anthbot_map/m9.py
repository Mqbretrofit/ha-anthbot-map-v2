"""Compatibility helpers for ANTHBOT M5/M9 cloud/shadow behavior.

Commands are written through the service named shadow. Live status --
including position (anti_loss_pose) and the live mowing trail (curpath) --
was assumed for a while to sometimes arrive on the *service* named shadow
instead of *property*, based on speculation without real M-series hardware
to check against. Anonymized real-M9 hardware data (captured 2026-08-19 from
341 service-shadow messages recorded live during an active
mow) disproved that: every live field showed up exclusively on the
*property* shadow, exactly like the base (non-M-series) devices this
integration already supports. The routing override this module used to
apply unconditionally has been narrowed to a defensive fallback -- see
``live_shadow`` below -- kept only in case some other M-series unit or
firmware really does behave differently; it does nothing on hardware that
matches what has actually been observed so far.

The same real M9 capture also disproved a second assumption: that curpath's
raw coordinates needed to be anchored to the live anti_loss_pose (assumed to
be a millimetre-to-metre conversion) to display correctly. In fact curpath
decodes through the exact same mgs-v1/v2/v3 path format -- and the exact
same ``decode_device_definition``/coordinate_scale handling -- that the base
integration already uses for downloaded historical path files, so it is
already in the map's native local coordinate system. The live curpath
range captured during that mow (x: -3180..-100, y: -40..21570) sits
squarely inside that same M9's own downloaded historical path range
(x: -3850..-20, y: -210..30330) -- same format, same scale, no anchoring
needed. Anchoring to anti_loss_pose was actively harmful whenever that field
was stale (the same capture showed it can freeze for an entire mowing
session while curpath keeps updating correctly), since it spliced a frozen,
unrelated coordinate into an otherwise-correct map-local trail.
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

_M_SERIES_SERIALS: set[str] = set()
_INSTALLED = False
_M_SERIES_MAP_PROBE_RETRY_SECONDS = 60.0
_M_SERIES_PATH_MAX_POINTS = 5000
_M_SERIES_MAP_CANDIDATES = ("multi_maps.tar.gz", "map_manager.tar.gz")

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
) -> dict[str, Any] | None:
    """Select the live pose, retaining the previous one for curpath deltas."""
    pose = _m_series_valid_pose(reported_pose)
    if pose is not None:
        return pose
    pose = _m_series_valid_pose(fallback_pose)
    if pose is not None:
        return pose
    return None


def _point_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    try:
        return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))
    except (KeyError, TypeError, ValueError):
        return float("inf")


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

    pose = _m_series_pose_for_update(normalized.get("pose"), fallback_pose)
    if pose is not None:
        normalized["pose"] = pose
        if _m_series_valid_pose(normalized.get("cur_pose")) is None:
            normalized["cur_pose"] = pose

    curpath = reported.get("curpath")
    decoded_curpath = _decode_live_curpath(curpath)
    if decoded_curpath is not None:
        # decode_device_definition() already applies the mgs format's own
        # coordinate_scale to every point (see api.py's _decode_path_
        # definition), so these x/y values are already in the map's native
        # local coordinate system -- the same frame the base integration's
        # downloaded area/ridable_area/path files use. No anchoring to the
        # live pose is needed or wanted; see the module docstring for the
        # real M9 evidence behind this.
        path_points = _m_series_display_path_points(decoded_curpath.get("_path_points"))
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
            normalized["_path_definition_error"] = (
                "M-series curpath decoded but contained no usable points"
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
        if is_m_series:
            _M_SERIES_SERIALS.add(self.client.serial_number)
            setattr(self, "_m_series_path_accumulator", [])
            setattr(self, "_m_series_path_id", None)
            setattr(self, "_m_series_last_pose", None)

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        # An anonymized real-M9 capture from 2026-08-19
        # reports live position/path fields (curpath, anti_loss_pose, mode,
        # ...) exclusively on the *property* named shadow -- exactly like
        # Genie/base devices, and unlike the speculative "M5/M9 uses
        # service" premise this module used to assume unconditionally. The
        # base coordinator routes shadow_name == "service" updates into the
        # nested ``reported_state["_service_reported"]`` bucket instead of
        # the top-level state that Map/status readers (sensor.py, mower_
        # status.py) actually read, so *if* a service-shadow message ever
        # does carry live fields on some other M-series unit/firmware, it
        # still needs rerouting to be visible -- but forcing that
        # unconditionally, as before, meant every ordinary service-shadow
        # message (command acks, etc.) also got merged into the property
        # bucket, which could overwrite fresher property data with stale or
        # unrelated content. This now only reroutes when the service message
        # actually contains live fields.
        origin_shadow_name = shadow_name
        if _is_m_series(getattr(self.device, "model", None)) and isinstance(reported, dict):
            fallback_pose = getattr(self, "_m_series_last_pose", None)
            if _m_series_valid_pose(fallback_pose) is None:
                fallback_pose = self.reported_state.get("pose")
            normalized = _normalize_m_series_reported(reported, fallback_pose=fallback_pose)
            # Check the RAW payload for a live pose, not normalized["pose"]:
            # the latter can be filled in from the cached fallback pose even
            # when this particular message carries no pose data at all,
            # which would make every message look like it has live fields.
            raw_anti_loss = reported.get("anti_loss_pose")
            raw_pose2d = raw_anti_loss.get("pose2d") if isinstance(raw_anti_loss, dict) else None
            has_live_fields = (
                normalized.get("_m_series_curpath_definition") is not None
                or _m_series_valid_pose(raw_pose2d) is not None
            )

            if origin_shadow_name == "service" and has_live_fields:
                _LOGGER.warning(
                    "ANTHBOT M-SERIES: live position/path fields found on the SERVICE shadow "
                    "for serial=%s -- this contradicts every M-series unit verified so far "
                    "(property-only). Merging them in anyway; please report this so the "
                    "compat layer can be corrected for this unit/firmware.",
                    self.client.serial_number,
                )

            if origin_shadow_name == "property" or has_live_fields:
                reported = normalized
                shadow_name = "property"
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
                        # A new path_id means the mower started a new mowing/
                        # mapping task -- the trail restarts from scratch.
                        # There is deliberately no distance-based "jump"
                        # heuristic here anymore: that existed only to paper
                        # over jumps caused by anchoring the trail to a
                        # separately-moving (and sometimes frozen) live pose.
                        # Now that curpath stays in its own stable, native
                        # map-local coordinate frame the whole time, path_id
                        # is the only signal that actually means "this is a
                        # different trail."
                        accumulator = list(packet_points)
                        setattr(self, "_m_series_path_id", path_id)
                    elif packet_points:
                        if not accumulator:
                            accumulator = list(packet_points)
                        elif _point_distance(accumulator[-1], packet_points[-1]) > 0:
                            accumulator.append(packet_points[-1])
                    accumulator = accumulator[-_M_SERIES_PATH_MAX_POINTS:]
                    setattr(self, "_m_series_path_accumulator", accumulator)

                    decoded = dict(decoded)
                    decoded["_path_points"] = accumulator
                    decoded["point_count"] = len(accumulator)
                    reported["_m_series_curpath_definition"] = decoded
                    reported["_path_definition"] = decoded
                    reported["path"] = accumulator
                    reported["mowed_path"] = accumulator
                    reported["cloud_path"] = accumulator

            # else: origin_shadow_name == "service" with no live fields --
            # leave `reported`/`shadow_name` untouched so it flows into the
            # normal service bucket, exactly like a non-M-series device.
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
