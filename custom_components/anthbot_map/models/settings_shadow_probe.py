"""Temporary safe live diagnostics for ANTHBOT settings persistence tests.

For M-series property updates this probe also records the complete *safe scalar
shape* of the shadow so previously unknown setting names can be discovered.
Credentials, URLs, map/path/position payloads, identifiers and large values are
excluded. Genie keeps the narrower selected-settings probe.
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

# Never log these families from the broad discovery probe. Matching is
# intentionally conservative because this is diagnostic code running on a
# user's real mower/account.
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
    """Keep safe scalar leaves and small nested dicts; discard bulk payloads."""
    if depth > 3:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        # Settings are normally short enums/strings. Avoid dumping arbitrary
        # text or encoded payloads.
        return value if len(value) <= 80 else None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if any(part in lowered for part in _BLOCKED_KEY_PARTS):
                continue
            safe = _safe_scalar_shape(item, depth=depth + 1)
            if safe is not None and (not isinstance(safe, dict) or safe):
                out[key] = safe
        return out or None
    # Lists/tuples are deliberately excluded: mower geometry and paths are
    # commonly represented as arrays.
    return None


def _safe_m_series_property(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    safe = _safe_scalar_shape(state)
    return safe if isinstance(safe, dict) else {}


def _diff(previous: Any, current: Any, prefix: str = "") -> dict[str, dict[str, Any]]:
    """Return leaf changes between two dictionaries."""
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
    """Attach safe setting diagnostics to each coordinator's live callback."""
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
            if selected:
                cache = dict(getattr(self, "_settings_probe_last", {}))
                previous = cache.get(name)
                if selected != previous:
                    changes = _diff(previous, selected) if previous is not None else {}
                    _LOGGER.warning(
                        "ANTHBOT SETTINGS PROBE sn=%s model=%s shadow=%s values=%s changes=%s",
                        self.client.serial_number, model, name, selected, changes,
                    )
                    cache[name] = selected
                    setattr(self, "_settings_probe_last", cache)

            # M9/M5 discovery mode: inspect every safe scalar property field,
            # allowing us to learn an unknown official-app setting name without
            # logging map/path/position/account/auth data.
            if name == "property" and _is_m_series(model):
                broad = _safe_m_series_property(reported)
                broad_cache = dict(getattr(self, "_settings_probe_broad_last", {}))
                previous_broad = broad_cache.get(name)
                if broad and broad != previous_broad:
                    broad_changes = _diff(previous_broad, broad) if previous_broad is not None else {}
                    _LOGGER.warning(
                        "ANTHBOT M-SERIES PROPERTY DIFF sn=%s model=%s changes=%s",
                        self.client.serial_number, model, broad_changes,
                    )
                    broad_cache[name] = broad
                    setattr(self, "_settings_probe_broad_last", broad_cache)

            await original(name, reported)

        setattr(listener, "_on_shadow", capture)
        setattr(listener, "_settings_probe_wrapped", True)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator.async_start_live_shadow = start_live_shadow
