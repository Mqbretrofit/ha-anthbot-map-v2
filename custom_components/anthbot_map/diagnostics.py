"""Diagnostics support for Anthbot Map."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


_SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "secret",
    "credential",
    "authorization",
    "username",
    "email",
    "url",
)


def _safe_diagnostic_value(value: Any) -> Any:
    """Recursively retain map geometry while removing secrets and URLs."""
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                safe[key] = "<redacted>"
            else:
                safe[key] = _safe_diagnostic_value(item)
        return safe
    if isinstance(value, (list, tuple)):
        return [_safe_diagnostic_value(item) for item in value]
    if isinstance(value, str) and value.lower().startswith(("http://", "https://", "ws://", "wss://")):
        return "<redacted>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _map_definition_summary(value: Any) -> Any:
    """Return map archive metadata without embedding the large raster."""
    if not isinstance(value, dict):
        return _safe_diagnostic_value(value)
    raster = value.get("_map_raster") or value.get("map_raster")
    raster_summary = None
    if isinstance(raster, dict):
        runs = raster.get("runs")
        raster_summary = {
            key: _safe_diagnostic_value(raster.get(key))
            for key in ("encoding", "width", "height", "resolution", "bounds")
            if raster.get(key) is not None
        }
        raster_summary["runs_length"] = len(runs) if isinstance(runs, list) else None
    return {
        "encoding": value.get("encoding"),
        "download_source": _safe_diagnostic_value(value.get("_download_source")),
        "map_raster": raster_summary,
    }


def _redact_serial(value: Any, serial_number: str) -> Any:
    """Remove the mower serial number from nested diagnostic values."""
    if isinstance(value, dict):
        return {key: _redact_serial(item, serial_number) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_serial(item, serial_number) for item in value]
    if isinstance(value, str) and serial_number:
        return value.replace(serial_number, "<serial>")
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return safe map and boundary diagnostics for a config entry."""
    coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id, [])
    mowers: list[dict[str, Any]] = []

    for coordinator in coordinators:
        state = coordinator.reported_state
        serial_number = coordinator.client.serial_number
        mower = {
            "serial_number": "<redacted>",
            "area_time": state.get("area_time"),
            "map_time": state.get("map_time"),
            "map_tar_time": state.get("map_tar_time"),
            "area_definition": _safe_diagnostic_value(
                state.get("_area_definition")
            ),
            "map_archive_selection": _safe_diagnostic_value(
                state.get("_map_archive_selection")
            ),
            "map_definition_summary": _map_definition_summary(
                state.get("_map_definition")
            ),
            "map_definition_error": state.get("_map_definition_error"),
        }
        mowers.append(_redact_serial(mower, serial_number))

    return {
        "integration": DOMAIN,
        "entry_title": entry.title,
        "mowers": mowers,
    }
