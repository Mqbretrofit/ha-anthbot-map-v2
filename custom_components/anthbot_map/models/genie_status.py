"""Genie live-status propagation matching the M-series HA update path.

Genie can publish robot status changes on the ``service`` named shadow while
M-series models normally expose their live status on the property path.  The
shared coordinator intentionally keeps service shadow data namespaced under
``_service_reported``.  That is correct for command acknowledgements, but it
also means Genie status changes do not become normal Home Assistant state
updates until a later full refresh.

Promote only known telemetry/status fields from Genie service-shadow packets
into the coordinator's pending property update.  The existing coalesced live
flush then publishes them through ``async_set_updated_data`` exactly like the
M-series property path, so dashboards receive a normal ``state_changed`` event
without reloading the page.
"""

from __future__ import annotations

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


def _genie_live_telemetry(reported: dict[str, Any]) -> dict[str, Any]:
    """Extract only state-bearing fields from one Genie service packet."""
    promoted = {
        key: value
        for key, value in reported.items()
        if key in _GENIE_LIVE_TELEMETRY_KEYS
    }

    # Some firmware wraps the reported service payload one level deeper.
    nested = reported.get("data")
    if isinstance(nested, dict):
        for key, value in nested.items():
            if key in _GENIE_LIVE_TELEMETRY_KEYS:
                promoted[key] = value
    return promoted


def install_genie_live_status_support() -> None:
    """Publish Genie live service-shadow telemetry as normal HA state updates."""
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
            shadow_name == "service"
            and isinstance(reported, dict)
            and model_family(getattr(self.device, "model", None)) == "genie"
        ):
            promoted = _genie_live_telemetry(reported)
            if promoted:
                # Feed the exact same coalesced property path used by the
                # M-series live state. The original handler below still keeps
                # the complete service packet under _service_reported.
                self._pending_live_property.update(promoted)

        await previous_live(self, shadow_name, reported)

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
