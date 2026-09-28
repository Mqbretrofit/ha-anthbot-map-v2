"""Temporary safe live diagnostics for ANTHBOT settings persistence tests.

Logs only selected non-sensitive property/service shadow fields and their
changes. No credentials, URLs, map geometry, position or account data are
logged. Intended for comparing official-app setting changes on Genie/M-series.
"""

from __future__ import annotations

import logging
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_MISSING = object()

_WANTED_TOP_LEVEL = (
    "param_set", "nest_param_set", "pobctl", "mow_count", "cutter_height",
    "cutter_level", "pobctl_level", "pobctl_switch", "obstacle_avoid_level",
    "visual_obstacle_level", "enable_adaptive_head", "mow_head", "mow_mode",
)
_WANTED_PARAM_FIELDS = (
    "mow_count", "cutter_height", "cutter_level", "pobctl_level",
    "pobctl_switch", "obstacle_avoid_level", "visual_obstacle_level",
    "enable_adaptive_head", "mow_head", "mow_mode", "nest_switch", "rid_switch",
)


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


def _diff(previous: Any, current: Any, prefix: str = "") -> dict[str, dict[str, Any]]:
    """Return leaf changes between two selected dictionaries."""
    before = previous if isinstance(previous, dict) else {}
    after = current if isinstance(current, dict) else {}
    changes: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        old = before.get(key, _MISSING)
        new = after.get(key, _MISSING)
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(old, dict) or isinstance(new, dict):
            changes.update(
                _diff(old if isinstance(old, dict) else {}, new if isinstance(new, dict) else {}, path)
            )
            continue
        if old != new:
            changes[path] = {
                "previous": "<missing>" if old is _MISSING else old,
                "current": "<missing>" if new is _MISSING else new,
            }
    return changes


def install_settings_shadow_probe() -> None:
    """Attach a selected-field logger to each coordinator's live shadow callback."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: AnthbotGenieDataUpdateCoordinator, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        setattr(self, "_settings_probe_last", {})

    previous_start = AnthbotGenieDataUpdateCoordinator.async_start_live_shadow

    async def start_live_shadow(self: AnthbotGenieDataUpdateCoordinator) -> None:
        await previous_start(self)
        listener = getattr(self, "_live_listener", None)
        original = getattr(listener, "_on_shadow", None)
        if listener is None or not callable(original) or getattr(listener, "_settings_probe_wrapped", False):
            return

        async def capture(name: str, reported: dict[str, Any]) -> None:
            selected = _selected(reported)
            if selected:
                cache = dict(getattr(self, "_settings_probe_last", {}))
                previous = cache.get(name)
                if selected != previous:
                    model = str(getattr(self.device, "model", "") or "")
                    changes = _diff(previous, selected) if previous is not None else {}
                    _LOGGER.warning(
                        "ANTHBOT SETTINGS PROBE sn=%s model=%s shadow=%s values=%s changes=%s",
                        self.client.serial_number, model, name, selected, changes,
                    )
                    cache[name] = selected
                    setattr(self, "_settings_probe_last", cache)
            await original(name, reported)

        setattr(listener, "_on_shadow", capture)
        setattr(listener, "_settings_probe_wrapped", True)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator.async_start_live_shadow = start_live_shadow
