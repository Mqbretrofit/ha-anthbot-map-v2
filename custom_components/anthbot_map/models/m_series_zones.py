"""M-series zone definitions from the current map-manager archive.

Field capture from a real M9 Pro (2026-09-04) confirms that app-created zones
are not exposed by the legacy Genie ``area_<serial>`` file. They live inside
``map_manager_<serial>.tar.gz`` as ``area_setting.json``. The property shadow's
``map.area_id`` changes when that area configuration is updated, even when the
outer ``map_id`` itself stays unchanged.

This layer deliberately reuses the already-proven M-series map-manager download
instead of introducing another cloud endpoint. It patches the downloader to
cache ``area_setting.json`` and wraps the M-series map refresh so an ``area_id``
change forces one fresh archive download. The decoded area definition is then
published through the coordinator's normal Home Assistant state path.
"""

from __future__ import annotations

import io
import json
import logging
import tarfile
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from . import m_series_map

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_AREA_CACHE: dict[str, dict[str, Any]] = {}


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _area_id_from_state(state: dict[str, Any]) -> str | None:
    value = state.get("map")
    if not isinstance(value, dict):
        return None
    area_id = value.get("area_id")
    if area_id in (None, ""):
        return None
    return str(area_id)


def _decode_area_setting(raw: bytes) -> dict[str, Any] | None:
    """Return ``area_setting.json`` from one M-series map-manager archive."""
    if not raw:
        return None
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                if member.name.rsplit("/", 1)[-1] != "area_setting.json":
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    return None
                payload = json.loads(extracted.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    return None
                # The captured M9 Pro format uses custom_areas for manual zones
                # and also carries forbid/dump-grass area lists in this file.
                for key in (
                    "custom_areas",
                    "forbid_areas",
                    "remote_forbid_areas",
                    "dump_grass_areas",
                ):
                    value = payload.get(key)
                    if value is not None and not isinstance(value, list):
                        return None
                return payload
    except (tarfile.TarError, OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return None


def _publish_area_definition(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    definition: dict[str, Any],
) -> bool:
    """Install one area definition and emit an immediate HA state update."""
    changed = definition != coordinator._area_definition  # noqa: SLF001 - model adapter
    coordinator._area_definition = definition  # noqa: SLF001 - model adapter
    if changed and coordinator.reported_state:
        state = dict(coordinator.reported_state)
        state["_area_definition"] = definition
        coordinator.async_set_updated_data(state)
    return changed


def install_m_series_zone_support() -> None:
    """Load app-created M-series zones from ``area_setting.json``."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_download = m_series_map._download_current_map_manager
    previous_refresh = AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition

    async def download_current_map_manager(
        account_client: Any,
        serial: str,
    ) -> tuple[bytes, dict[str, Any]]:
        raw, source_info = await previous_download(account_client, serial)
        area_definition = _decode_area_setting(raw)
        if area_definition is not None:
            cached = dict(area_definition)
            cached["_download_source"] = {
                **source_info,
                "member": "area_setting.json",
            }
            _AREA_CACHE[serial] = cached
        return raw, source_info

    async def refresh_map_definition(
        self: AnthbotGenieDataUpdateCoordinator,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        model = getattr(self.device, "model", None)
        if not _is_m_series(model):
            return await previous_refresh(
                self,
                property_state,
                now,
                allow_periodic=allow_periodic,
            )

        area_id = _area_id_from_state(property_state)
        loaded_area_id = getattr(self, "_m_series_area_id", None)

        # The outer map can remain unchanged while the app replaces only its
        # area_setting.json. Force the proven map-manager layer to fetch the
        # fixed archive name again whenever map.area_id changes.
        if area_id is not None and area_id != loaded_area_id:
            setattr(self, "_m_series_vector_map_id", None)
            setattr(self, "_m_series_vector_map_probe_last", 0.0)

        diagnostics, attempted = await previous_refresh(
            self,
            property_state,
            now,
            allow_periodic=allow_periodic,
        )

        cached = _AREA_CACHE.get(self.client.serial_number)
        if isinstance(cached, dict):
            changed = _publish_area_definition(self, cached)
            decoded_area_id = cached.get("area_id")
            effective_area_id = (
                str(decoded_area_id)
                if decoded_area_id not in (None, "")
                else area_id
            )
            setattr(self, "_m_series_area_id", effective_area_id)
            diagnostics = dict(diagnostics)
            diagnostics["area_id"] = effective_area_id
            diagnostics["manual_zone_count"] = len(
                cached.get("custom_areas")
                if isinstance(cached.get("custom_areas"), list)
                else []
            )
            diagnostics["area_definition_source"] = "map_manager:area_setting.json"
            if changed:
                _LOGGER.info(
                    "ANTHBOT M-SERIES: loaded %s app zones from area_setting.json for %s (%s), area_id=%s",
                    diagnostics["manual_zone_count"],
                    self.client.serial_number,
                    model,
                    effective_area_id,
                )
        elif area_id is not None:
            # Do not mark an unseen area_id as loaded: retaining the old value
            # makes the next refresh retry the archive instead of silently
            # accepting a missing/invalid area_setting.json.
            diagnostics = dict(diagnostics)
            diagnostics["area_id"] = area_id
            diagnostics["area_definition_source"] = "map_manager:area_setting.json-unavailable"

        return diagnostics, attempted

    # m_series_map resolves this module-global at call time, so wrapping it here
    # lets map and zone decoding share exactly one archive download.
    m_series_map._download_current_map_manager = download_current_map_manager
    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition
