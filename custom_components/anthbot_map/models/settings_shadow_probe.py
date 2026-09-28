"""Temporary safe live diagnostics for ANTHBOT settings persistence tests.

Logs only selected non-sensitive property/service shadow fields when the mower
publishes them.  No credentials, URLs, map geometry, position or account data
are logged.  Intended for comparing official-app setting changes on Genie and
M-series robots.
"""

from __future__ import annotations

import logging
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False

_WANTED_TOP_LEVEL = (
    "param_set",
    "nest_param_set",
    "pobctl",
    "mow_count",
    "cutter_height",
    "cutter_level",
    "pobctl_level",
    "pobctl_switch",
    "obstacle_avoid_level",
    "visual_obstacle_level",
    "enable_adaptive_head",
    "mow_head",
    "mow_mode",
)
_WANTED_PARAM_FIELDS = (
    "mow_count",
    "cutter_height",
    "cutter_level",
    "pobctl_level",
    "pobctl_switch",
    "obstacle_avoid_level",
    "visual_obstacle_level",
    "enable_adaptive_head",
    "mow_head",
    "mow_mode",
    "nest_switch",
    "rid_switch",
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
                previous = getattr(self, "_settings_probe_last", {}).get(name)
                if selected != previous:
                    model = str(getattr(self.device, "model", "") or "")
                    _LOGGER.warning(
                        "ANTHBOT SETTINGS PROBE sn=%s model=%s shadow=%s values=%s",
                        self.client.serial_number,
                        model,
                        name,
                        selected,
                    )
                    cache = dict(getattr(self, "_settings_probe_last", {}))
                    cache[name] = selected
                    setattr(self, "_settings_probe_last", cache)
            await original(name, reported)

        setattr(listener, "_on_shadow", capture)
        setattr(listener, "_settings_probe_wrapped", True)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator.async_start_live_shadow = start_live_shadow
