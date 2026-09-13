"""Recorder compatibility repairs for Anthbot Map v2.4.6.7.

Two field-observed Recorder churn sources are handled here without slowing real
map telemetry:

* Home Assistant combines an entity class' ``_unrecorded_attributes`` during
  class construction and caches the result in a private combined set. Runtime
  performance diagnostics are added later by a compatibility layer, so the
  cached set must be rebuilt explicitly before Map entities are created.
* v2.4.6.5 deliberately caps the always-ready Map entity at one Home Assistant
  state write every five seconds. That protects live-map responsiveness, but an
  unchanged idle map can still create thousands of identical Recorder rows per
  day. This layer suppresses only unchanged Map writes while preserving the
  existing five-second limiter for real map/pose/status changes. A one-minute
  heartbeat keeps diagnostic/current-state metadata reasonably fresh while the
  mower is otherwise idle.
"""

from __future__ import annotations

import time
from typing import Any

_INSTALLED = False
_MAP_UNCHANGED_HEARTBEAT_SECONDS = 60.0
_MISSING = object()


def _small_mapping_signature(value: Any) -> tuple[Any, ...] | Any:
    """Return a cheap stable signature for small pose/status-like mappings."""
    if not isinstance(value, dict):
        return value
    keys = (
        "x",
        "y",
        "z",
        "yaw",
        "heading",
        "angle",
        "lat",
        "lon",
        "latitude",
        "longitude",
        "value",
        "status",
        "state",
    )
    return tuple((key, repr(value.get(key))) for key in keys if key in value)


def _path_signature(path_definition: Any, fallback_path: Any) -> tuple[Any, ...]:
    """Track path growth/replacement without copying the full point list."""
    if isinstance(path_definition, dict):
        points = path_definition.get("_path_points")
        metadata = tuple(
            repr(path_definition.get(key))
            for key in (
                "path_id",
                "start",
                "task_type",
                "point_count",
                "coordinate_scale",
            )
        )
    else:
        points = fallback_path
        metadata = ()

    if not isinstance(points, list):
        return (metadata, None, 0, None)
    last = points[-1] if points else None
    return (metadata, id(points), len(points), _small_mapping_signature(last))


def _map_live_signature(sensor_module: Any, coordinator: Any) -> tuple[Any, ...]:
    """Return the Map/UI-relevant revision signature for one coordinator state."""
    state = coordinator.reported_state
    path_definition = state.get("_path_definition")
    map_definition = state.get("_map_definition")
    area_definition = state.get("_area_definition")
    ridable_definition = state.get("_ridable_area_definition")

    return (
        sensor_module._general_mower_status(state),
        sensor_module._raw_robot_status(state),
        _small_mapping_signature(state.get("pose")),
        _small_mapping_signature(state.get("curPose") or state.get("cur_pose")),
        _small_mapping_signature(
            state.get("mapScanPose") or state.get("map_scan_pose")
        ),
        _path_signature(path_definition, state.get("path")),
        id(map_definition),
        repr(state.get("map_time")),
        repr(state.get("path_time")),
        repr(state.get("area_time")),
        repr(state.get("ridable_area_time")),
        id(area_definition),
        id(ridable_definition),
        repr(state.get("_map_definition_error")),
        repr(state.get("_path_definition_error")),
        repr(state.get("_ridable_area_definition_error")),
        bool(state.get("_cloud_connected")),
        bool(state.get("_robot_online")),
        bool(state.get("_live_shadow_connected", False)),
        repr(state.get("_cloud_error")),
        repr(state.get("_live_shadow_error")),
        id(state.get("_mowing_records")),
        id(state.get("_task_events")),
        id(state.get("_error_history")),
        _small_mapping_signature(state.get("robot_maintenance")),
        bool(coordinator.custom_button_actions_configured),
        bool(coordinator.custom_button_actions_enabled),
        id(coordinator.custom_button_actions),
    )


def _install_unchanged_map_write_filter(sensor_module: Any) -> None:
    """Skip identical Map writes but retain v2.4.6.5's five-second live limit."""
    map_entity = sensor_module.AnthbotMapSensorEntity
    previous_update = map_entity._handle_coordinator_update

    def handle_coordinator_update(self: Any) -> None:
        now = time.monotonic()
        signature = _map_live_signature(sensor_module, self.coordinator)
        previous_signature = getattr(
            self, "_anthbot_v2467_map_signature", _MISSING
        )
        last_actual_write = float(
            getattr(self, "_anthbot_last_map_state_write", 0.0) or 0.0
        )

        changed = previous_signature is _MISSING or signature != previous_signature
        heartbeat_due = (
            not last_actual_write
            or now - last_actual_write >= _MAP_UNCHANGED_HEARTBEAT_SECONDS
        )
        if not changed and not heartbeat_due:
            return

        # recorder_v2465 remains the final authority for the five-second live
        # throttle. Only remember the signature when that wrapped handler
        # actually wrote a Home Assistant state; otherwise the pending change
        # is retried on the next coordinator update.
        before_write = last_actual_write
        previous_update(self)
        after_write = float(
            getattr(self, "_anthbot_last_map_state_write", 0.0) or 0.0
        )
        if after_write != before_write:
            self._anthbot_v2467_map_signature = signature

    map_entity._handle_coordinator_update = handle_coordinator_update


def install_recorder_v2467() -> None:
    """Install the v2.4.6.7 Recorder fixes before Map entities are created."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from .. import sensor as sensor_module

    map_entity = sensor_module.AnthbotMapSensorEntity
    unrecorded = frozenset(
        set(map_entity._unrecorded_attributes) | {"runtime_performance"}
    )
    map_entity._unrecorded_attributes = unrecorded

    # Home Assistant computes this private cache in Entity.__init_subclass__.
    # The diagnostics compatibility layer modifies _unrecorded_attributes after
    # class creation, so explicitly refresh the same cache before entity setup.
    component_unrecorded = frozenset(
        getattr(map_entity, "_entity_component_unrecorded_attributes", frozenset())
    )
    map_entity._Entity__combined_unrecorded_attributes = (
        component_unrecorded | unrecorded
    )

    _install_unchanged_map_write_filter(sensor_module)
