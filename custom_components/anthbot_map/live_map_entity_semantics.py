"""Stable Home Assistant state semantics for the WebSocket live-map transport.

The dedicated WebSocket stream owns live map/path/pose delivery. The Map entity
is therefore only a compact status/diagnostic anchor and must not write a new
Home Assistant state for telemetry that is already delivered through the
stream.

Field testing showed that map archive diagnostics, error-history snapshots,
task events and other ancillary collections can legitimately rotate every few
seconds while mowing. They remain visible on the compact Map entity and are
refreshed by its one-minute heartbeat, but they do not trigger Recorder writes.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

_LOGGER = logging.getLogger(__name__)
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


def _rebind_existing_map_listener(coordinator: Any) -> int:
    """Rebind already-registered Map callbacks to the compact class handler.

    Home Assistant stores a bound coordinator callback when an entity is added.
    Changing the entity class method later does not replace that stored bound
    method. The sensor platform is forwarded before lawn_mower, so the Map
    entity may already be listening through the old Recorder wrapper when the
    live stream becomes available.

    Keep the existing listener id/context so Home Assistant's normal removal
    callback still removes the correct listener; only replace the callback
    object with the Map entity's now-patched compact handler.
    """
    from . import sensor as sensor_module

    listeners = getattr(coordinator, "_listeners", None)
    if not isinstance(listeners, dict):
        return 0

    rebound = 0
    map_entity_type = sensor_module.AnthbotMapSensorEntity
    for listener_id, listener_entry in list(listeners.items()):
        if not isinstance(listener_entry, tuple) or len(listener_entry) != 2:
            continue
        callback, context = listener_entry
        entity = getattr(callback, "__self__", None)
        if not isinstance(entity, map_entity_type):
            continue
        listeners[listener_id] = (entity._handle_coordinator_update, context)  # noqa: SLF001
        rebound += 1

    return rebound


def install_live_map_entity_write_semantics(
    coordinators: Iterable[Any] | None = None,
) -> int:
    """Apply compact semantics and rebind any Map listeners already registered."""
    global _INSTALLED

    from . import live_map_stream
    from .models import recorder_v2467

    if not _INSTALLED:
        # Existing Recorder callbacks resolve recorder_v2467._map_live_signature
        # dynamically. Newly patched compact callbacks likewise resolve the
        # module-global _compact_write_signature dynamically.
        live_map_stream._compact_write_signature = live_map_entity_write_signature  # noqa: SLF001
        recorder_v2467._map_live_signature = live_map_entity_write_signature  # noqa: SLF001
        _INSTALLED = True

    rebound = 0
    if coordinators is not None:
        for coordinator in coordinators:
            rebound += _rebind_existing_map_listener(coordinator)

    if rebound:
        _LOGGER.info(
            "ANTHBOT live map stream: rebound %s existing Map coordinator listener(s) "
            "to compact state semantics",
            rebound,
        )
    return rebound


__all__ = [
    "install_live_map_entity_write_semantics",
    "live_map_entity_write_signature",
]
