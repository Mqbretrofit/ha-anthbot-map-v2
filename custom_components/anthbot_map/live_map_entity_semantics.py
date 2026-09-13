"""Stable Home Assistant state semantics for the WebSocket live-map transport.

The dedicated WebSocket stream owns live map/path/pose delivery.  The Map
entity is therefore only a compact status/diagnostic anchor and must not write
a new Home Assistant state for telemetry that is already delivered through the
stream.

Field testing showed that map archive diagnostics, error-history snapshots,
task events and other ancillary collections can legitimately rotate every few
seconds while mowing.  They remain visible on the compact Map entity and are
refreshed by its one-minute heartbeat, but they do not trigger Recorder writes.
"""

from __future__ import annotations

from typing import Any

_INSTALLED = False


def live_map_entity_write_signature(
    sensor_module: Any,
    coordinator: Any,
) -> tuple[Any, ...]:
    """Return only immediate HA-state semantics for the compact Map entity.

    Live geometry and diagnostic/history collections are deliberately absent.
    The WebSocket stream delivers geometry immediately; the Map entity heartbeat
    keeps non-critical diagnostic metadata current without turning live mowing
    into Recorder churn.
    """
    from .models import recorder_v2467 as recorder

    state = coordinator.reported_state
    return (
        sensor_module._general_mower_status(state),  # noqa: SLF001
        sensor_module._raw_robot_status(state),  # noqa: SLF001
        bool(state.get("_cloud_connected")),
        bool(state.get("_robot_online")),
        bool(state.get("_live_shadow_connected", False)),
        recorder._stable_small(state.get("_cloud_error")),  # noqa: SLF001
        recorder._stable_small(state.get("_live_shadow_error")),  # noqa: SLF001
        recorder._stable_small(state.get("_map_definition_error")),  # noqa: SLF001
        recorder._stable_small(state.get("_path_definition_error")),  # noqa: SLF001
        recorder._stable_small(  # noqa: SLF001
            state.get("_ridable_area_definition_error")
        ),
        recorder._stable_small(state.get("robot_maintenance")),  # noqa: SLF001
        recorder._stable_small(coordinator.last_mowing_task),  # noqa: SLF001
        bool(coordinator.custom_button_actions_configured),
        bool(coordinator.custom_button_actions_enabled),
        recorder._stable_small(coordinator.custom_button_actions),  # noqa: SLF001
    )


def install_live_map_entity_write_semantics() -> None:
    """Apply the compact signature to both old and newly wrapped Map listeners."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from . import live_map_stream
    from .models import recorder_v2467

    # The sensor platform is set up before lawn_mower, so an existing Map
    # entity may already hold the recorder_v2467 wrapper.  That wrapper resolves
    # recorder_v2467._map_live_signature dynamically on every coordinator
    # update.  The live_map_stream wrapper likewise resolves its module-global
    # _compact_write_signature dynamically.  Replacing both functions therefore
    # updates existing listeners without removing/re-registering HA callbacks.
    live_map_stream._compact_write_signature = live_map_entity_write_signature  # noqa: SLF001
    recorder_v2467._map_live_signature = live_map_entity_write_signature  # noqa: SLF001


__all__ = [
    "install_live_map_entity_write_semantics",
    "live_map_entity_write_signature",
]
