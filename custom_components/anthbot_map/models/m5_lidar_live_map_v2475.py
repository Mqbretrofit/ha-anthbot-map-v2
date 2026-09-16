"""M5 LiDAR live-map preference for the post-v2.4.7.4 test line.

The Android 2.15.16 app requests the current M LiDAR map as
``map_<serial>.txt`` with ``category=device`` and ``sub_category=map``.
Keep that verified current-map path ahead of M-series map-manager/legacy
archive probes, but only for the LiDAR M5 family. Every existing M5/M9/N8/
Genie fallback remains installed underneath this wrapper unchanged.
"""

from __future__ import annotations

import logging
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..definition_refresh import (
    MAP_DEFINITION_REFRESH_SECONDS,
    MAP_DEFINITION_RETRY_SECONDS,
    map_archive_diagnostics,
    map_definition_cache_key,
    select_map_archive,
)

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False


def _is_m5_lidar(model: object) -> bool:
    """Return whether the friendly/raw model identifies the M5 LiDAR family."""
    value = " ".join(str(model or "").upper().replace("_", " ").replace("-", " ").split())
    compact = value.replace(" ", "")
    return (
        "MGS02RADAR" in compact
        or "MLIDARSERIES" in compact
        or ("M5" in compact and ("LIDAR" in compact or "RADAR" in compact))
    )


def _map_time(state: dict[str, Any]) -> str | None:
    value: Any = state.get("map_time")
    if isinstance(value, dict):
        value = value.get("value", value.get("time"))
    if value in (None, "") or isinstance(value, bool):
        return None
    return str(value)


def _live_signature(serial: str, state: dict[str, Any]) -> str:
    return f"map_{serial}.txt|map_time={_map_time(state) or ''}"


def _diagnostics(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any],
    *,
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selection = select_map_archive(state)
    diagnostics = map_archive_diagnostics(state, selection)
    diagnostics.update(
        {
            "preferred_source": "live_map",
            "active_source": str(
                getattr(coordinator, "_map_definition_source", "") or ""
            )
            or None,
            "live_file": f"map_{coordinator.client.serial_number}.txt",
            "live_map_time": _map_time(state),
            "m5_lidar_live_first": True,
        }
    )
    if isinstance(probe, dict):
        diagnostics["m5_lidar_live_map_probe"] = dict(probe)
    return diagnostics


def install_m5_lidar_live_map_fix() -> None:
    """Prefer the app-verified current live map only for M5 LiDAR devices."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_refresh = AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition

    async def refresh_map_definition(
        self: AnthbotGenieDataUpdateCoordinator,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        model = getattr(self.device, "model", None)
        if not _is_m5_lidar(model):
            return await previous_refresh(
                self,
                property_state,
                now,
                allow_periodic=allow_periodic,
            )

        serial = self.client.serial_number
        signature = _live_signature(serial, property_state)
        loaded_signature = getattr(self, "_m5_lidar_live_signature", None)
        source = str(getattr(self, "_map_definition_source", "") or "")
        definition = getattr(self, "_map_definition", None)
        has_live_map = (
            source == "live_map"
            and isinstance(definition, dict)
            and isinstance(definition.get("_map_raster"), dict)
        )

        last_probe = float(getattr(self, "_m5_lidar_live_probe_last", 0.0) or 0.0)
        last_success = float(
            getattr(self, "_m5_lidar_live_success_last", 0.0) or 0.0
        )
        signature_changed = loaded_signature != signature
        should_probe = (
            signature_changed
            or not has_live_map
            or (
                allow_periodic
                and last_success > 0.0
                and now - last_success >= MAP_DEFINITION_REFRESH_SECONDS
            )
        )
        if (
            should_probe
            and not signature_changed
            and last_probe > 0.0
            and now - last_probe < MAP_DEFINITION_RETRY_SECONDS
        ):
            should_probe = False

        if not should_probe and has_live_map:
            return _diagnostics(self, property_state), False

        probe: dict[str, Any] = {
            "attempted": bool(should_probe),
            "filename": f"map_{serial}.txt",
            "category": "device",
            "sub_category": "map",
        }
        if should_probe:
            setattr(self, "_m5_lidar_live_probe_last", now)
            try:
                refreshed = await self.account_client.async_get_device_map_definition(
                    serial
                )
            except Exception as err:  # noqa: BLE001 - preserve all existing fallbacks.
                probe.update(
                    {
                        "status": "error",
                        "error_type": type(err).__name__,
                        "error": str(err)[:240],
                    }
                )
                setattr(self, "_m5_lidar_live_error", str(err)[:240])
                _LOGGER.debug(
                    "ANTHBOT M5 LiDAR live map unavailable for %s: %s; preserving existing fallback chain",
                    serial,
                    err,
                )
                if has_live_map:
                    # A transient cloud error must not replace a valid current
                    # LiDAR map with an older archive.
                    return _diagnostics(self, property_state, probe=probe), True
            else:
                self._map_definition = refreshed
                self._map_definition_source = "live_map"
                self._map_definition_error = None
                self._last_map_download_monotonic = now
                self._last_map_time = _map_time(property_state)
                selection = select_map_archive(property_state)
                self._last_map_key = map_definition_cache_key(
                    serial,
                    property_state,
                    selection,
                )
                setattr(self, "_m5_lidar_live_signature", signature)
                setattr(self, "_m5_lidar_live_success_last", now)
                setattr(self, "_m5_lidar_live_error", None)
                probe["status"] = "decoded"
                source_info = (
                    refreshed.get("_download_source")
                    if isinstance(refreshed, dict)
                    else None
                )
                if isinstance(source_info, dict):
                    probe["download_source"] = {
                        key: source_info.get(key)
                        for key in (
                            "filename",
                            "category",
                            "sub_category",
                            "content_md5",
                        )
                        if source_info.get(key) not in (None, "")
                    }
                return _diagnostics(self, property_state, probe=probe), True

        # If the live file is absent/temporarily unavailable, do not invent a
        # replacement. Hand control back to the complete pre-existing stack:
        # serial-named map_manager, selected multi_maps archive, legacy rescue,
        # and every existing model-specific decoder remain untouched.
        diagnostics, attempted = await previous_refresh(
            self,
            property_state,
            now,
            allow_periodic=allow_periodic,
        )
        diagnostics = dict(diagnostics)
        diagnostics.setdefault("preferred_source", "live_map")
        diagnostics["m5_lidar_live_first"] = True
        diagnostics["m5_lidar_live_map_probe"] = probe
        return diagnostics, bool(attempted or should_probe)

    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = (
        refresh_map_definition
    )


__all__ = ["install_m5_lidar_live_map_fix"]
