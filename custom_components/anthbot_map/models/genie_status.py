"""Genie live-status normalization matching the M-series HA update path.

The M-series compatibility layer normalizes live mower status to the canonical
``robot_sta = {"value": ...}`` shape before the shared coordinator publishes a
Home Assistant update. Genie firmware can expose the same state as
``robot_sta``, ``mower_status`` or ``mode`` and may place it on either named
shadow. Normalize those variants before handing them to the shared coordinator
so the existing sensor/map entities update immediately without a page reload.
"""

from __future__ import annotations

import json
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from .base import model_family

_INSTALLED = False

# Deliberately narrow allow-list: never copy command/ack envelope fields such as
# cmd/data wholesale into the public robot state.
_GENIE_LIVE_TELEMETRY_KEYS: frozenset[str] = frozenset(
    {
        "robot_sta",
        "mower_status",
        "robot_status_raw",
        "mode",
        "elec",
        "mowing_area_new",
        "mowing_time_new",
        "mowing_progress",
        "progress_percent",
        "event_code",
        "err_code",
        "rtk_state",
        "rtk_base_state",
        "pose",
        "cur_pose",
        "online",
        "timestamp",
    }
)


def _unwrap_value(value: Any) -> Any:
    """Unwrap Anthbot ``{"value": ...}`` envelopes safely."""
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def _nested_payload(reported: dict[str, Any]) -> dict[str, Any]:
    """Return a service payload whether ``data`` is a dict or JSON string."""
    nested = reported.get("data")
    if isinstance(nested, dict):
        return nested
    if isinstance(nested, str):
        try:
            decoded = json.loads(nested)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _canonical_robot_status(reported: dict[str, Any]) -> Any:
    """Return live Genie status across the property/service payload variants."""
    candidates = [reported]
    nested = _nested_payload(reported)
    if nested:
        candidates.append(nested)

    for payload in candidates:
        for key in ("robot_sta", "mower_status", "mode"):
            value = _unwrap_value(payload.get(key))
            if isinstance(value, (str, int)):
                return value
    return None


def _normalize_genie_live_reported(reported: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Genie live packet to the canonical shared state shape."""
    normalized = dict(reported)
    status = _canonical_robot_status(reported)
    if status is not None:
        # sensor.py's established Genie status mapping expects the canonical
        # property-shadow envelope. This is exactly what the M-series layer
        # produces from its ``mode`` field.
        normalized["robot_sta"] = {"value": status}
    return normalized


def _genie_live_telemetry(reported: dict[str, Any]) -> dict[str, Any]:
    """Extract only state-bearing fields from one Genie service packet."""
    promoted = {
        key: value
        for key, value in reported.items()
        if key in _GENIE_LIVE_TELEMETRY_KEYS and key != "mode"
    }

    nested = _nested_payload(reported)
    for key, value in nested.items():
        if key in _GENIE_LIVE_TELEMETRY_KEYS and key != "mode":
            promoted[key] = value

    status = _canonical_robot_status(reported)
    if status is not None:
        promoted["robot_sta"] = {"value": status}
    return promoted


def install_genie_live_status_support() -> None:
    """Publish Genie live telemetry through the same HA path as M-series."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow

    async def live_shadow(
        self: AnthbotGenieDataUpdateCoordinator,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        if (
            isinstance(reported, dict)
            and model_family(getattr(self.device, "model", None)) == "genie"
        ):
            normalized = _normalize_genie_live_reported(reported)

            if shadow_name == "service":
                promoted = _genie_live_telemetry(normalized)
                if promoted:
                    # Service-shadow state must participate in the normal
                    # property update so CoordinatorEntity listeners emit the
                    # same immediate state_changed events as M-series.
                    self._pending_live_property.update(promoted)

            # Property packets also need canonicalization. In particular some
            # Genie firmware reports live state as ``mode`` or as a scalar
            # ``robot_sta``; the legacy sensor ignored those shapes.
            reported = normalized

        await previous_live(self, shadow_name, reported)

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
