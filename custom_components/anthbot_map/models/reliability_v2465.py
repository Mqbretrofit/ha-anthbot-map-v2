"""Reliability and Recorder fixes for v2.4.6.5.

This layer is intentionally installed after the v2.4.6.4 reliability patch.
It keeps mower/model control untouched and addresses four field issues:
- duplicate automatic diagnostics caused by unstable cloud error signatures,
- excessive Recorder churn from shared fast-changing entity attributes,
- overly frequent diagnostic position/tracker state writes,
- M-series map-manager archives whose iot_map.bin uses the raster/LZ4 format.
"""

from __future__ import annotations

import hashlib
import io
import re
import tarfile
import time
from typing import Any

from .. import api as api_module
from ..coordinator import AnthbotGenieDataUpdateCoordinator
from . import m_series_map

_INSTALLED = False
_PLATFORM_PATCHED = False
_DIAGNOSTIC_CLEAR_GRACE_SECONDS = 60.0
_DIAGNOSTIC_HARD_REPEAT_SECONDS = 60.0 * 60.0
_POSITION_STATE_MIN_SECONDS = 10.0

_MAP_PROBE_BY_SERIAL: dict[str, dict[str, Any]] = {}

_COMMON_SENSOR_ATTRIBUTES = {
    "mower_status",
    "robot_status_raw",
    "cutting_height",
    "mowing_time",
    "mowing_area",
    "custom_mowing_direction",
    "custom_mowing_direction_enabled",
    "voice_volume",
    "voice_status",
    "rain_continue_time",
}

_POSITION_SENSOR_KEYS = {
    "pose_x",
    "pose_y",
    "pose_yaw",
    "gps_latitude",
    "gps_longitude",
}

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_REQUEST_ID_RE = re.compile(r"<RequestId>.*?</RequestId>", re.IGNORECASE | re.DOTALL)
_HOST_ID_RE = re.compile(r"<HostId>.*?</HostId>", re.IGNORECASE | re.DOTALL)


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _stable_error_text(value: object) -> str:
    """Remove request-specific cloud noise while preserving the actual error."""
    text = str(value or "")
    text = _URL_RE.sub("<url>", text)
    text = _REQUEST_ID_RE.sub("<RequestId>", text)
    text = _HOST_ID_RE.sub("<HostId>", text)
    return " ".join(text.split())[:2048]


def _stable_error_signature(trigger: str, value: object) -> str:
    normalized = _stable_error_text(value)
    digest = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:20]
    return f"{trigger}:{digest}"


def _extract_iot_map(raw: bytes) -> tuple[bytes | None, list[str]]:
    if not raw:
        return None, []
    members: list[str] = []
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                members.append(member.name)
                if member.name.rsplit("/", 1)[-1] != "iot_map.bin":
                    continue
                extracted = archive.extractfile(member)
                if extracted is not None:
                    return extracted.read(), members
    except (tarfile.TarError, OSError, EOFError, ValueError):
        return None, members
    return None, members


def _install_m_series_raster_fallback_and_probe() -> None:
    """Accept both verified M-series iot_map.bin encodings and expose safe probe data."""
    previous_decoder = m_series_map._decode_map_manager_archive  # noqa: SLF001
    previous_download = m_series_map._download_current_map_manager  # noqa: SLF001
    previous_refresh = AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition

    def decode_map_manager_archive(raw: bytes, model: object = None) -> dict[str, Any] | None:
        decoded = previous_decoder(raw, model=model)
        if isinstance(decoded, dict):
            decoded.setdefault("map_manager_decode", "vector")
            return decoded

        iot_map, members = _extract_iot_map(raw)
        if not iot_map:
            return None
        raster = api_module._decode_map_raster(iot_map)  # noqa: SLF001
        if not isinstance(raster, dict):
            return None
        raster = dict(raster)
        raster["robot_image_asset"] = m_series_map._model_robot_asset(model)  # noqa: SLF001
        return {
            "format": "m-series-iot-map-raster-v1",
            "map_manager_decode": "raster_lz4",
            "iot_map_size": len(iot_map),
            "archive_members": members,
            "_map_raster": raster,
        }

    async def download_current_map_manager(
        account_client: Any,
        serial: str,
    ) -> tuple[bytes, dict[str, Any]]:
        probe: dict[str, Any] = {
            "attempted": True,
            "filename": f"map_manager_{serial}.tar.gz",
            "category": "device",
            "sub_category": "map",
            "download_status": "started",
        }
        try:
            raw, source = await previous_download(account_client, serial)
        except Exception as err:  # noqa: BLE001 - preserve original fallback behavior.
            probe["download_status"] = "error"
            probe["error"] = _stable_error_text(err)
            _MAP_PROBE_BY_SERIAL[serial] = probe
            raise

        iot_map, members = _extract_iot_map(raw)
        probe.update(
            {
                "download_status": "downloaded",
                "archive_size": len(raw),
                "archive_members": members,
                "iot_map_present": iot_map is not None,
                "iot_map_size": len(iot_map) if iot_map is not None else 0,
            }
        )
        if isinstance(source, dict):
            for key in ("filename", "category", "sub_category"):
                if source.get(key) not in (None, ""):
                    probe[key] = source.get(key)
        _MAP_PROBE_BY_SERIAL[serial] = probe
        return raw, source

    async def refresh_map_definition(
        self: AnthbotGenieDataUpdateCoordinator,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        diagnostics, attempted = await previous_refresh(
            self,
            property_state,
            now,
            allow_periodic=allow_periodic,
        )
        if not _is_m_series(getattr(self.device, "model", None)):
            return diagnostics, attempted

        probe = _MAP_PROBE_BY_SERIAL.get(self.client.serial_number)
        if not isinstance(probe, dict):
            return diagnostics, attempted

        safe_probe = dict(probe)
        source = str(getattr(self, "_map_definition_source", "") or "")
        definition = getattr(self, "_map_definition", None)
        if source.startswith("m_series_map_manager:") and isinstance(definition, dict):
            safe_probe["decode_status"] = "decoded"
            safe_probe["decode_format"] = definition.get("format")
        elif safe_probe.get("download_status") == "downloaded":
            safe_probe["decode_status"] = "unrecognized"

        diagnostics = dict(diagnostics)
        diagnostics["map_manager_probe"] = safe_probe
        return diagnostics, attempted

    m_series_map._decode_map_manager_archive = decode_map_manager_archive  # noqa: SLF001
    m_series_map._download_current_map_manager = download_current_map_manager  # noqa: SLF001
    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition


def _patch_platform_modules() -> None:
    """Patch report deduplication and entity update behavior after imports settle."""
    global _PLATFORM_PATCHED
    if _PLATFORM_PATCHED:
        return
    _PLATFORM_PATCHED = True

    from .. import binary_sensor as binary_sensor_module
    from .. import button as button_module
    from .. import device_tracker as device_tracker_module
    from .. import sensor as sensor_module

    previous_trigger = button_module._automatic_diagnostics_trigger  # noqa: SLF001

    def stable_automatic_diagnostics_trigger(
        state: dict[str, Any],
    ) -> tuple[str, str] | None:
        detected = previous_trigger(state)
        if detected is None:
            return None
        trigger, signature = detected
        if trigger == "no_go_path_crossing":
            check = state.get("_no_go_path_check")
            if isinstance(check, dict):
                path_id = check.get("path_id")
                zone_ids = check.get("zone_ids")
                zone_key = ",".join(
                    sorted(str(item) for item in zone_ids)
                ) if isinstance(zone_ids, list) else ""
                return trigger, f"no-go:{path_id}:{zone_key}"
            return trigger, signature
        error_key = {
            "path_definition_error": "_path_definition_error",
            "map_definition_error": "_map_definition_error",
            "live_shadow_error": "_live_shadow_error",
        }.get(trigger)
        if error_key is not None:
            return trigger, _stable_error_signature(trigger, state.get(error_key))
        return trigger, signature

    button_module._automatic_diagnostics_trigger = stable_automatic_diagnostics_trigger  # noqa: SLF001

    def install_episode_aware_automatic_diagnostics(
        hass: Any,
        entry: Any,
        coordinator: AnthbotGenieDataUpdateCoordinator,
    ) -> None:
        # Platform reloads must never add a second listener to the same coordinator.
        existing = getattr(coordinator, "_anthbot_auto_diag_listener_remove", None)
        if callable(existing):
            return

        initial_state = coordinator.reported_state
        initial = (
            stable_automatic_diagnostics_trigger(initial_state)
            if isinstance(initial_state, dict)
            else None
        )
        coordinator._anthbot_auto_diag_active_signature = (  # type: ignore[attr-defined]
            initial[1] if initial is not None else None
        )
        coordinator._anthbot_auto_diag_clear_since = None  # type: ignore[attr-defined]
        if not isinstance(
            getattr(coordinator, "_anthbot_auto_diag_last_sent", None), dict
        ):
            coordinator._anthbot_auto_diag_last_sent = {}  # type: ignore[attr-defined]

        def handle_update() -> None:
            if not button_module._entry_option_enabled(  # noqa: SLF001
                entry,
                button_module.CONF_SEND_AUTOMATIC_DIAGNOSTICS,
            ):
                return
            installation_id = entry.data.get(
                button_module.CONF_DEVELOPER_INSTALLATION_ID
            )
            if not isinstance(installation_id, str) or not installation_id:
                return
            state = coordinator.reported_state
            if not isinstance(state, dict):
                return

            now = time.monotonic()
            detected = stable_automatic_diagnostics_trigger(state)
            active_signature = getattr(
                coordinator, "_anthbot_auto_diag_active_signature", None
            )
            clear_since = getattr(coordinator, "_anthbot_auto_diag_clear_since", None)

            if detected is None:
                if active_signature is not None and clear_since is None:
                    coordinator._anthbot_auto_diag_clear_since = now  # type: ignore[attr-defined]
                return

            trigger, signature = detected
            if clear_since is not None:
                if now - float(clear_since) >= _DIAGNOSTIC_CLEAR_GRACE_SECONDS:
                    active_signature = None
                    coordinator._anthbot_auto_diag_active_signature = None  # type: ignore[attr-defined]
                coordinator._anthbot_auto_diag_clear_since = None  # type: ignore[attr-defined]

            # Active mower errors have their own reporter and must not be doubled.
            if trigger == "mower_error_code":
                coordinator._anthbot_auto_diag_active_signature = signature  # type: ignore[attr-defined]
                return
            if signature == active_signature:
                return

            sent_at = coordinator._anthbot_auto_diag_last_sent  # type: ignore[attr-defined]
            previous = sent_at.get(signature)
            coordinator._anthbot_auto_diag_active_signature = signature  # type: ignore[attr-defined]
            if previous is not None and now - float(previous) < _DIAGNOSTIC_HARD_REPEAT_SECONDS:
                return

            report = button_module.build_firmware_diagnostics_report(
                coordinator,
                include_raw_state=False,
                include_identifiers=False,
            )
            sent_at[signature] = now
            session = button_module.async_get_clientsession(hass)
            hass.async_create_task(
                button_module.async_send_diagnostics_report(
                    session,
                    button_module.DEVELOPER_DIAGNOSTICS_ENDPOINT,
                    installation_id=installation_id,
                    report=report,
                    trigger=trigger,
                )
            )

        unsubscribe = coordinator.async_add_listener(handle_update)
        coordinator._anthbot_auto_diag_listener_remove = unsubscribe  # type: ignore[attr-defined]

        def remove_listener() -> None:
            current = getattr(coordinator, "_anthbot_auto_diag_listener_remove", None)
            if callable(current):
                current()
            coordinator._anthbot_auto_diag_listener_remove = None  # type: ignore[attr-defined]

        entry.async_on_unload(remove_listener)

    button_module._install_automatic_diagnostics_reporting = (  # noqa: SLF001
        install_episode_aware_automatic_diagnostics
    )

    original_sensor_attributes = sensor_module.AnthbotSensorEntity.extra_state_attributes.fget
    if original_sensor_attributes is not None:
        def sensor_attributes(self: Any) -> dict[str, Any]:
            attributes = dict(original_sensor_attributes(self))
            for key in _COMMON_SENSOR_ATTRIBUTES:
                attributes.pop(key, None)
            attributes.pop("latest_task_event_age_seconds", None)
            status = attributes.get("latest_task_event_status")
            if isinstance(status, dict):
                status = dict(status)
                status.pop("age_seconds", None)
                attributes["latest_task_event_status"] = status

            entity_key = self.entity_description.key
            if entity_key in {"mowing_progress", "active_zone_area"}:
                keep = {
                    "serial_number",
                    "progress_source",
                    "progress_target_area_m2",
                    "progress_mowing_area_m2",
                    "progress_map_area_m2",
                }
                attributes = {key: value for key, value in attributes.items() if key in keep}
            return attributes

        sensor_module.AnthbotSensorEntity.extra_state_attributes = property(sensor_attributes)

    original_sensor_update = sensor_module.AnthbotSensorEntity._handle_coordinator_update

    def sensor_handle_coordinator_update(self: Any) -> None:
        if self.entity_description.key in _POSITION_SENSOR_KEYS:
            now = time.monotonic()
            last = float(getattr(self, "_anthbot_last_position_write", 0.0) or 0.0)
            if last and now - last < _POSITION_STATE_MIN_SECONDS:
                return
            self._anthbot_last_position_write = now
        original_sensor_update(self)

    sensor_module.AnthbotSensorEntity._handle_coordinator_update = sensor_handle_coordinator_update

    original_map_attributes = sensor_module.AnthbotMapSensorEntity.extra_state_attributes.fget
    if original_map_attributes is not None:
        def map_attributes(self: Any) -> dict[str, Any]:
            attributes = dict(original_map_attributes(self))
            # This timestamp changes on every live shadow flush and was enough to
            # create a Recorder row even while the mower/map itself was unchanged.
            attributes.pop("cloud_last_success", None)
            return attributes

        sensor_module.AnthbotMapSensorEntity.extra_state_attributes = property(map_attributes)

    original_binary_attributes = binary_sensor_module.AnthbotBinarySensorEntity.extra_state_attributes.fget
    if original_binary_attributes is not None:
        def binary_attributes(self: Any) -> dict[str, Any]:
            attributes = dict(original_binary_attributes(self))
            entity_key = self.entity_description.key
            if entity_key in {"rain_hold"}:
                return attributes
            if entity_key == "no_go_path_crossing":
                if self.is_on:
                    return attributes
                return {
                    key: value
                    for key, value in attributes.items()
                    if key in {"serial_number", "model"}
                }
            return {
                "serial_number": self.coordinator.client.serial_number,
            }

        binary_sensor_module.AnthbotBinarySensorEntity.extra_state_attributes = property(binary_attributes)

    original_tracker_attributes = device_tracker_module.AnthbotLocationTracker.extra_state_attributes.fget
    if original_tracker_attributes is not None:
        def tracker_attributes(self: Any) -> dict[str, Any]:
            attributes = dict(original_tracker_attributes(self))
            return {
                key: value
                for key, value in attributes.items()
                if key in {"serial_number", "pose_type"}
            }

        device_tracker_module.AnthbotLocationTracker.extra_state_attributes = property(tracker_attributes)

    original_tracker_update = device_tracker_module.AnthbotLocationTracker._handle_coordinator_update

    def tracker_handle_coordinator_update(self: Any) -> None:
        now = time.monotonic()
        last = float(getattr(self, "_anthbot_last_location_write", 0.0) or 0.0)
        if last and now - last < _POSITION_STATE_MIN_SECONDS:
            return
        self._anthbot_last_location_write = now
        original_tracker_update(self)

    device_tracker_module.AnthbotLocationTracker._handle_coordinator_update = tracker_handle_coordinator_update


def _install_deferred_platform_patch() -> None:
    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: Any, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        _patch_platform_modules()

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init


def install_v2465_reliability_fixes() -> None:
    """Install v2.4.6.5 fixes after all earlier model/reliability layers."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _install_m_series_raster_fallback_and_probe()
    _install_deferred_platform_patch()
