"""ANTHBOT N8 map-manager, area-setting and plan-setting support.

N8 uses the MGS map-manager archive family but is kept outside the proven
M5/M9/M9 Pro activation guards. This adapter reuses the already-tested binary
and area-setting decoders while activating them only for N8 models.

The same archive also carries ``time_setting.json`` in the current MGS app.
That file is parsed read-only here into a privacy-safe structural summary so
live N8 diagnostics can validate plan/DND firmware formats without enabling
schedule writes.
"""

from __future__ import annotations

import io
import json
import logging
import tarfile
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from . import m_series_map, m_series_zones
from .n8_control import is_n8_model

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_RETRY_SECONDS = 60.0


def _decode_n8_time_setting(raw: bytes) -> dict[str, Any] | None:
    """Extract the current MGS ``time_setting.json`` from map-manager bytes."""
    if not raw:
        return None
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                if member.name.rsplit("/", 1)[-1] != "time_setting.json":
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    return None
                payload = json.loads(extracted.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else None
    except (
        tarfile.TarError,
        OSError,
        EOFError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None
    return None


def _summarize_n8_time_setting(payload: dict[str, Any]) -> dict[str, Any]:
    """Return schema evidence without exporting personal schedule times.

    Static 2.15.16 analysis shows full plan envelopes with
    ``timezone/timezone_sec/value`` and incremental envelopes adding
    ``version``. The live probe records only counts, key sets and scalar
    envelope metadata; individual start/end times are deliberately omitted.
    """
    value = payload.get("value")
    entries = value if isinstance(value, list) else []
    dnd_count = 0
    appointment_count = 0
    entry_key_sets: set[tuple[str, ...]] = set()

    for item in entries:
        if not isinstance(item, dict):
            continue
        entry_key_sets.add(tuple(sorted(str(key) for key in item)))
        if item.get("unlock") == 0:
            dnd_count += 1
        else:
            appointment_count += 1

    summary: dict[str, Any] = {
        "top_level_keys": sorted(str(key) for key in payload),
        "entry_count": len(entries),
        "dnd_count": dnd_count,
        "appointment_count": appointment_count,
        "entry_key_sets": [list(keys) for keys in sorted(entry_key_sets)],
    }
    for key in ("timezone", "timezone_sec", "version"):
        value = payload.get(key)
        if value is None or isinstance(value, (bool, int, float, str)):
            if key in payload:
                summary[key] = value
    return summary


def install_n8_map_support() -> None:
    """Install N8-only map-manager, area and read-only plan refresh support."""
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
        if not is_n8_model(model):
            return await previous_refresh(
                self,
                property_state,
                now,
                allow_periodic=allow_periodic,
            )

        map_id = m_series_map._map_id_from_state(property_state)  # noqa: SLF001
        area_id = m_series_zones._area_id_from_state(property_state)  # noqa: SLF001
        loaded_map_id = getattr(self, "_n8_map_id", None)
        loaded_area_id = getattr(self, "_n8_area_id", None)
        last_probe = float(getattr(self, "_n8_map_probe_last", 0.0) or 0.0)

        map_changed = map_id is not None and map_id != loaded_map_id
        area_changed = area_id is not None and area_id != loaded_area_id
        should_probe = (
            last_probe == 0.0
            or now - last_probe >= _RETRY_SECONDS
            or map_changed
            or area_changed
        )

        attempted = False
        diagnostics: dict[str, Any] = {
            "preferred_source": "n8_map_manager",
            "map_id": loaded_map_id,
            "area_id": loaded_area_id,
        }

        if should_probe:
            attempted = True
            setattr(self, "_n8_map_probe_last", now)
            try:
                # m_series_zones wraps this downloader globally after map support
                # is installed, so one N8 archive fetch also fills its area cache.
                raw, source_info = await m_series_map._download_current_map_manager(  # noqa: SLF001
                    self.account_client,
                    self.client.serial_number,
                )
                definition = m_series_map._decode_map_manager_archive(  # noqa: SLF001
                    raw,
                    model=model,
                )
                if definition is None:
                    raise RuntimeError(
                        "N8 map_manager downloaded but iot_map.bin was not recognized"
                    )

                definition["_download_source"] = source_info
                self._map_definition = definition  # noqa: SLF001
                self._map_definition_source = (  # noqa: SLF001
                    f"n8_map_manager:{source_info['filename']}"
                )
                self._map_definition_error = None  # noqa: SLF001
                self._last_map_download_monotonic = now  # noqa: SLF001

                decoded_map_id = str(definition.get("map_id") or map_id or "") or None
                setattr(self, "_n8_map_id", decoded_map_id)
                diagnostics.update(
                    {
                        "active_source": self._map_definition_source,  # noqa: SLF001
                        "map_id": decoded_map_id,
                        "boundary_points": definition.get("point_count"),
                        "boundary_area_m2": definition.get("polygon_area_m2"),
                    }
                )

                cached = m_series_zones._AREA_CACHE.get(  # noqa: SLF001
                    self.client.serial_number
                )
                if isinstance(cached, dict):
                    m_series_zones._publish_area_definition(self, cached)  # noqa: SLF001
                    decoded_area_id = cached.get("area_id")
                    effective_area_id = (
                        str(decoded_area_id)
                        if decoded_area_id not in (None, "")
                        else area_id
                    )
                    setattr(self, "_n8_area_id", effective_area_id)
                    diagnostics.update(
                        {
                            "area_id": effective_area_id,
                            "manual_zone_count": len(
                                cached.get("custom_areas")
                                if isinstance(cached.get("custom_areas"), list)
                                else []
                            ),
                            "dump_grass_area_count": len(
                                cached.get("dump_grass_areas")
                                if isinstance(cached.get("dump_grass_areas"), list)
                                else []
                            ),
                            "area_definition_source": "map_manager:area_setting.json",
                        }
                    )

                time_setting = _decode_n8_time_setting(raw)
                if isinstance(time_setting, dict):
                    time_summary = _summarize_n8_time_setting(time_setting)
                    setattr(self, "_n8_time_setting_summary", time_summary)
                    diagnostics.update(
                        {
                            "time_setting_present": True,
                            "plan_entry_count": time_summary.get("entry_count", 0),
                            "dnd_count": time_summary.get("dnd_count", 0),
                            "plan_version": time_summary.get("version"),
                            "time_setting_source": "map_manager:time_setting.json",
                        }
                    )
                else:
                    setattr(self, "_n8_time_setting_summary", None)
                    diagnostics.update(
                        {
                            "time_setting_present": False,
                            "time_setting_source": "map_manager:time_setting.json-unavailable",
                        }
                    )

                _LOGGER.info(
                    "ANTHBOT N8: loaded map_manager for %s (%s), zones=%s dump_areas=%s plans=%s dnd=%s",
                    self.client.serial_number,
                    model,
                    diagnostics.get("manual_zone_count", 0),
                    diagnostics.get("dump_grass_area_count", 0),
                    diagnostics.get("plan_entry_count", 0),
                    diagnostics.get("dnd_count", 0),
                )
                return diagnostics, True
            except Exception as err:  # noqa: BLE001 - preserve base fallback.
                diagnostics["error"] = str(err)
                _LOGGER.warning(
                    "ANTHBOT N8: map_manager refresh failed for %s (%s): %s",
                    self.client.serial_number,
                    model,
                    err,
                )

        # Keep all beta.9 fallback behavior if N8 archive download/decoding is
        # unavailable. This call is intentionally after the N8 attempt only.
        fallback, fallback_attempted = await previous_refresh(
            self,
            property_state,
            now,
            allow_periodic=allow_periodic,
        )
        if isinstance(fallback, dict):
            diagnostics["fallback"] = fallback
        return diagnostics, attempted or fallback_attempted

    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = refresh_map_definition


__all__ = [
    "_decode_n8_time_setting",
    "_summarize_n8_time_setting",
    "install_n8_map_support",
]
