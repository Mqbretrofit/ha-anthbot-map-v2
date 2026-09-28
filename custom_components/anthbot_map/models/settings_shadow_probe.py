"""Temporary safe live diagnostics for ANTHBOT settings persistence tests.

M-series shadow updates can be partial. Merge safe scalar fragments into the
previous snapshot and report only meaningful setting changes. Timestamp noise,
credentials, URLs, identifiers and map/path/position payloads are excluded.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_MISSING = object()

_WANTED_TOP_LEVEL = (
    "param_set", "nest_param_set", "device_config", "pobctl", "mow_count",
    "cutter_height", "cutter_level", "pobctl_level", "pobctl_switch",
    "obstacle_avoid_level", "visual_obstacle_level", "enable_adaptive_head",
    "mow_head", "mow_mode",
)
_WANTED_PARAM_FIELDS = (
    "mow_count", "cutter_height", "cutter_level", "pobctl_level",
    "pobctl_switch", "obstacle_avoid_level", "visual_obstacle_level",
    "enable_adaptive_head", "mow_head", "mow_mode", "nest_switch", "rid_switch",
)
_BLOCKED_KEY_PARTS = (
    "token", "secret", "credential", "password", "passwd", "auth", "sign",
    "cert", "key", "url", "uri", "endpoint", "host", "account", "email",
    "phone", "user", "owner", "serial", "sn", "uuid", "device_id", "imei",
    "mac", "wifi", "ssid", "ip", "location", "position", "coordinate",
    "latitude", "longitude", "gps", "map", "path", "track", "trajectory",
    "boundary", "polygon", "point", "area", "zone", "image", "picture",
    "file", "blob", "raw", "history", "record", "log",
)


def _is_m_series(model: Any) -> bool:
    text = str(model or "").upper()
    return "M9" in text or "M5" in text


def _selected(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    result: dict[str, Any] = {}
    for key in _WANTED_TOP_LEVEL:
        value = state.get(key)
        if key in {"param_set", "nest_param_set"}:
            if isinstance(value, dict):
                picked = {name: value[name] for name in _WANTED_PARAM_FIELDS if name in value}
                if picked:
                    result[key] = picked
        elif key == "device_config":
            if isinstance(value, dict):
                picked = {
                    name: value[name]
                    for name in (
                        "pobctl_level", "pobctl_switch", "obstacle_avoid_level",
                        "visual_obstacle_level",
                    )
                    if name in value
                }
                if picked:
                    result[key] = picked
        elif key == "pobctl":
            if isinstance(value, dict):
                picked = {name: value[name] for name in ("switch", "level", "value") if name in value}
                if picked:
                    result[key] = picked
            elif value is not None:
                result[key] = value
        elif value is not None and isinstance(value, (bool, int, float, str)):
            result[key] = value
    return result


def _safe_scalar_shape(value: Any, *, depth: int = 0) -> Any:
    if depth > 3:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 80 else None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if lowered in {"time", "timestamp", "ts"} or lowered.endswith("_time"):
                continue
            if any(part in lowered for part in _BLOCKED_KEY_PARTS):
                continue
            safe = _safe_scalar_shape(item, depth=depth + 1)
            if safe is not None and (not isinstance(safe, dict) or safe):
                out[key] = safe
        return out or None
    return None


def _safe_m_series_property(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    safe = _safe_scalar_shape(state)
    return safe if isinstance(safe, dict) else {}


def _safe_service_command(state: Any) -> dict[str, Any]:
    """Keep only command-shaped, non-sensitive service-shadow fields."""
    if not isinstance(state, dict):
        return {}
    result: dict[str, Any] = {}
    for key in ("cmd", "command", "data", "value", "code"):
        if key not in state:
            continue
        safe = _safe_scalar_shape(state[key])
        if safe is not None:
            result[key] = safe
    return result


def _deep_merge(base: Any, patch: Any) -> dict[str, Any]:
    result = dict(base) if isinstance(base, dict) else {}
    if not isinstance(patch, dict):
        return result
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        elif isinstance(value, dict):
            result[key] = _deep_merge({}, value)
        else:
            result[key] = value
    return result


def _diff(previous: Any, current: Any, prefix: str = "") -> dict[str, dict[str, Any]]:
    before = previous if isinstance(previous, dict) else {}
    after = current if isinstance(current, dict) else {}
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        old = before.get(key, _MISSING)
        new = after.get(key, _MISSING)
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(old, dict) or isinstance(new, dict):
            changes.update(_diff(old if isinstance(old, dict) else {}, new if isinstance(new, dict) else {}, path))
            continue
        if old != new:
            changes[path] = {
                "previous": "<missing>" if old is _MISSING else old,
                "current": "<missing>" if new is _MISSING else new,
            }
    return changes


async def _capture_service_after_visual_change(coordinator: Any, level: Any) -> None:
    """Sample the actual service shadow immediately after an official-app change."""
    # Give AWS IoT a fraction of a second to settle the matching service shadow.
    await asyncio.sleep(0.15)
    try:
        service = await coordinator.client._async_get_named_shadow_reported_state("service")
    except asyncio.CancelledError:
        raise
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "ANTHBOT M9 VISUAL SERVICE PROBE sn=%s level=%s result=read_failed error=%s",
            coordinator.client.serial_number, level, type(err).__name__,
        )
        return
    command = _safe_service_command(service)
    _LOGGER.warning(
        "ANTHBOT M9 VISUAL SERVICE PROBE sn=%s level=%s service=%s",
        coordinator.client.serial_number, level, command or "<no-command-fields>",
    )


def install_settings_shadow_probe() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: AnthbotGenieDataUpdateCoordinator, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        setattr(self, "_settings_probe_last", {})
        setattr(self, "_settings_probe_broad_last", {})

    previous_start = AnthbotGenieDataUpdateCoordinator.async_start_live_shadow

    async def start_live_shadow(self: AnthbotGenieDataUpdateCoordinator) -> None:
        await previous_start(self)
        listener = getattr(self, "_live_listener", None)
        original = getattr(listener, "_on_shadow", None)
        if listener is None or not callable(original) or getattr(listener, "_settings_probe_wrapped", False):
            return

        async def capture(name: str, reported: dict[str, Any]) -> None:
            model = str(getattr(self.device, "model", "") or "")
            selected = _selected(reported)
            visual_change_level = _MISSING
            if selected:
                cache = dict(getattr(self, "_settings_probe_last", {}))
                previous = cache.get(name)
                merged_selected = _deep_merge(previous, selected) if previous is not None else selected
                if merged_selected != previous:
                    changes = _diff(previous, merged_selected) if previous is not None else {}
                    if previous is not None and changes:
                        _LOGGER.warning(
                            "ANTHBOT SETTINGS PROBE sn=%s model=%s shadow=%s changes=%s",
                            self.client.serial_number, model, name, changes,
                        )
                        visual = changes.get("device_config.pobctl_level")
                        if isinstance(visual, dict):
                            visual_change_level = visual.get("current", _MISSING)
                    cache[name] = merged_selected
                    setattr(self, "_settings_probe_last", cache)

            if name == "property" and _is_m_series(model):
                fragment = _safe_m_series_property(reported)
                broad_cache = dict(getattr(self, "_settings_probe_broad_last", {}))
                previous_broad = broad_cache.get(name)
                merged_broad = _deep_merge(previous_broad, fragment) if previous_broad is not None else fragment
                if merged_broad and merged_broad != previous_broad:
                    broad_changes = _diff(previous_broad, merged_broad) if previous_broad is not None else {}
                    if previous_broad is not None and broad_changes:
                        _LOGGER.warning(
                            "ANTHBOT M-SERIES PROPERTY DIFF sn=%s model=%s shadow=%s changes=%s",
                            self.client.serial_number, model, name, broad_changes,
                        )
                    broad_cache[name] = merged_broad
                    setattr(self, "_settings_probe_broad_last", broad_cache)

            if visual_change_level is not _MISSING and _is_m_series(model):
                self.hass.async_create_task(
                    _capture_service_after_visual_change(self, visual_change_level)
                )

            await original(name, reported)

        setattr(listener, "_on_shadow", capture)
        setattr(listener, "_settings_probe_wrapped", True)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator.async_start_live_shadow = start_live_shadow
