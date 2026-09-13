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
  day because ``runtime_performance`` keeps changing in the live state. This
  layer suppresses only semantically unchanged Map writes while preserving the
  existing five-second limiter for real map/pose/status changes. A one-minute
  heartbeat keeps diagnostics/current-state metadata reasonably fresh while the
  mower is otherwise idle.

The change detector intentionally uses semantic content summaries rather than
Python object identity. Coordinator refreshes may rebuild equivalent dict/list
objects, so ``id(...)`` would falsely classify unchanged data as new data.
"""

from __future__ import annotations

import json
import time
from typing import Any

_INSTALLED = False
_MAP_UNCHANGED_HEARTBEAT_SECONDS = 60.0
_MISSING = object()


def _stable_small(value: Any) -> Any:
    """Return a stable representation for small diagnostic/config values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
    except (TypeError, ValueError, OverflowError):
        return repr(value)


def _small_mapping_signature(value: Any) -> tuple[Any, ...] | Any:
    """Return a cheap stable signature for pose/status-like mappings."""
    if not isinstance(value, dict):
        return _stable_small(value)
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
    return tuple((key, _stable_small(value.get(key))) for key in keys if key in value)


def _sequence_edge_signature(value: Any) -> tuple[Any, ...] | Any:
    """Summarise changing record/event lists without copying entire histories."""
    if isinstance(value, dict):
        for key in ("data", "items", "events", "records"):
            child = value.get(key)
            if isinstance(child, list):
                return (
                    key,
                    len(child),
                    _stable_small(child[0]) if child else None,
                    _stable_small(child[-1]) if child else None,
                )
        identity_keys = (
            "id",
            "code",
            "type",
            "status",
            "state",
            "time",
            "timestamp",
            "event_time",
            "task_id",
            "path_id",
        )
        selected = tuple(
            (key, _stable_small(value.get(key)))
            for key in identity_keys
            if key in value
        )
        return ("dict", tuple(sorted(str(key) for key in value)), selected)
    if isinstance(value, (list, tuple)):
        return (
            "sequence",
            len(value),
            _stable_small(value[0]) if value else None,
            _stable_small(value[-1]) if value else None,
        )
    return _stable_small(value)


def _path_signature(path_definition: Any, fallback_path: Any) -> tuple[Any, ...]:
    """Track path growth/replacement without copying the full point list."""
    if isinstance(path_definition, dict):
        points = path_definition.get("_path_points")
        metadata = tuple(
            _stable_small(path_definition.get(key))
            for key in (
                "path_id",
                "start",
                "task_type",
                "point_count",
                "coordinate_scale",
                "_download_source",
            )
        )
    else:
        points = fallback_path
        metadata = ()

    if not isinstance(points, list):
        return (metadata, 0, None, None)
    return (
        metadata,
        len(points),
        _small_mapping_signature(points[0]) if points else None,
        _small_mapping_signature(points[-1]) if points else None,
    )


def _map_definition_signature(value: Any) -> tuple[Any, ...] | Any:
    """Summarise map/raster metadata while avoiding the large raster payload."""
    if not isinstance(value, dict):
        return _stable_small(value)
    raster = value.get("_map_raster") or value.get("map_raster")
    raster_signature: Any = None
    if isinstance(raster, dict):
        runs = raster.get("runs")
        raster_signature = (
            _stable_small(raster.get("encoding")),
            _stable_small(raster.get("width")),
            _stable_small(raster.get("height")),
            _stable_small(raster.get("resolution")),
            _stable_small(raster.get("bounds")),
            len(runs) if isinstance(runs, list) else None,
            _stable_small(runs[0]) if isinstance(runs, list) and runs else None,
            _stable_small(runs[-1]) if isinstance(runs, list) and runs else None,
        )
    return (
        tuple(sorted(str(key) for key in value.keys())),
        _stable_small(value.get("encoding")),
        _stable_small(value.get("_download_source")),
        raster_signature,
    )


def _area_definition_signature(value: Any) -> tuple[Any, ...] | Any:
    """Summarise zone geometry by stable collection edges and counts."""
    if not isinstance(value, dict):
        return _stable_small(value)
    collection_keys = (
        "areas",
        "work_areas",
        "manual_areas",
        "auto_areas",
        "forbid_areas",
        "no_go_areas",
        "ridable_areas",
        "edges",
    )
    collections = tuple(
        (key, _sequence_edge_signature(value.get(key)))
        for key in collection_keys
        if key in value
    )
    scalar_keys = (
        "id",
        "map_id",
        "version",
        "time",
        "timestamp",
        "area_time",
    )
    scalars = tuple(
        (key, _stable_small(value.get(key)))
        for key in scalar_keys
        if key in value
    )
    return (tuple(sorted(str(key) for key in value.keys())), scalars, collections)


def _map_live_signature(sensor_module: Any, coordinator: Any) -> tuple[Any, ...]:
    """Return the Map/UI-relevant semantic revision signature."""
    state = coordinator.reported_state
    path_definition = state.get("_path_definition")

    return (
        sensor_module._general_mower_status(state),
        sensor_module._raw_robot_status(state),
        _small_mapping_signature(state.get("pose")),
        _small_mapping_signature(state.get("curPose") or state.get("cur_pose")),
        _small_mapping_signature(
            state.get("mapScanPose") or state.get("map_scan_pose")
        ),
        _path_signature(path_definition, state.get("path")),
        _map_definition_signature(state.get("_map_definition")),
        _stable_small(state.get("map_time")),
        _stable_small(state.get("path_time")),
        _stable_small(state.get("area_time")),
        _stable_small(state.get("ridable_area_time")),
        _area_definition_signature(state.get("_area_definition")),
        _area_definition_signature(state.get("_ridable_area_definition")),
        _stable_small(state.get("_history_path_info")),
        _stable_small(state.get("_history_path_source")),
        _stable_small(state.get("_history_path_live_refresh")),
        _stable_small(state.get("_history_path_refresh_interval")),
        _stable_small(state.get("_map_archive_selection")),
        _stable_small(state.get("_map_definition_error")),
        _stable_small(state.get("_path_definition_error")),
        _stable_small(state.get("_ridable_area_definition_error")),
        bool(state.get("_cloud_connected")),
        bool(state.get("_robot_online")),
        bool(state.get("_live_shadow_connected", False)),
        _stable_small(state.get("_cloud_error")),
        _stable_small(state.get("_live_shadow_error")),
        _sequence_edge_signature(state.get("_mowing_records")),
        _sequence_edge_signature(state.get("_task_events")),
        _sequence_edge_signature(state.get("_error_history")),
        _stable_small(state.get("robot_maintenance")),
        _stable_small(coordinator.last_mowing_task),
        bool(coordinator.custom_button_actions_configured),
        bool(coordinator.custom_button_actions_enabled),
        _stable_small(coordinator.custom_button_actions),
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
        # actually accepted a Home Assistant state write; otherwise a pending
        # real change is retried on the next coordinator update.
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
