"""Field-proven idle Recorder semantics for Anthbot Map v2.4.6.7.

A live Recorder probe showed that an idle mower still changed Map writes every
few seconds because volatile ``map_time`` metadata, its derived archive
selection diagnostics, and event-heavy ``_error_history`` were treated as
Map/UI semantic changes.

This layer keeps those values available in live state, but makes the v2.4.6.7
Map write filter react only to stable archive identity and real error fields.
Actual map geometry, path, pose, status, task records and connection/error state
remain part of the write signature.
"""

from __future__ import annotations

from typing import Any

from . import recorder_v2467 as _recorder

_INSTALLED = False


def _archive_identity(value: Any) -> tuple[Any, ...] | Any:
    """Ignore rotating timestamps while retaining actual archive identity."""
    if not isinstance(value, dict):
        return _recorder._stable_small(value)  # noqa: SLF001
    keys = (
        "selected_file",
        "selected_md5",
        "selected_map_id",
        "map_count",
        "preferred_source",
        "active_source",
        "map_id",
        "boundary_points",
        "boundary_area_m2",
        "experimental",
    )
    return tuple(
        (key, _recorder._stable_small(value.get(key)))  # noqa: SLF001
        for key in keys
        if key in value
    )


def _actual_error_history_signature(value: Any) -> tuple[Any, ...] | Any:
    """Track real errors, not timestamps or generic mower event traffic."""
    if not isinstance(value, (list, tuple)):
        return _recorder._stable_small(value)  # noqa: SLF001

    errors: list[tuple[Any, ...]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        fields = tuple(
            (key, _recorder._stable_small(item.get(key)))  # noqa: SLF001
            for key in ("error", "err_code", "error_code")
            if item.get(key) not in (None, 0, "", [], {})
        )
        if fields:
            errors.append(fields)

    return (
        "actual_errors",
        len(errors),
        errors[0] if errors else None,
        errors[-1] if errors else None,
    )


def _stable_map_live_signature(sensor_module: Any, coordinator: Any) -> tuple[Any, ...]:
    """Return Map/UI semantics without field-proven idle-only churn sources."""
    state = coordinator.reported_state
    path_definition = state.get("_path_definition")

    return (
        sensor_module._general_mower_status(state),
        sensor_module._raw_robot_status(state),
        _recorder._small_mapping_signature(state.get("pose")),  # noqa: SLF001
        _recorder._small_mapping_signature(  # noqa: SLF001
            state.get("curPose") or state.get("cur_pose")
        ),
        _recorder._small_mapping_signature(  # noqa: SLF001
            state.get("mapScanPose") or state.get("map_scan_pose")
        ),
        _recorder._path_signature(path_definition, state.get("path")),  # noqa: SLF001
        _recorder._map_definition_signature(state.get("_map_definition")),  # noqa: SLF001
        # map_time is intentionally omitted. Field data shows it rotates while
        # the mower/map geometry is idle. The dedicated map timestamp sensor
        # still exposes it, while real map changes are covered above.
        _recorder._stable_small(state.get("path_time")),  # noqa: SLF001
        _recorder._stable_small(state.get("area_time")),  # noqa: SLF001
        _recorder._stable_small(state.get("ridable_area_time")),  # noqa: SLF001
        _recorder._area_definition_signature(state.get("_area_definition")),  # noqa: SLF001
        _recorder._area_definition_signature(  # noqa: SLF001
            state.get("_ridable_area_definition")
        ),
        _recorder._stable_small(state.get("_history_path_info")),  # noqa: SLF001
        _recorder._stable_small(state.get("_history_path_source")),  # noqa: SLF001
        _recorder._stable_small(state.get("_history_path_live_refresh")),  # noqa: SLF001
        _recorder._stable_small(state.get("_history_path_refresh_interval")),  # noqa: SLF001
        _archive_identity(state.get("_map_archive_selection")),
        _recorder._stable_small(state.get("_map_definition_error")),  # noqa: SLF001
        _recorder._stable_small(state.get("_path_definition_error")),  # noqa: SLF001
        _recorder._stable_small(state.get("_ridable_area_definition_error")),  # noqa: SLF001
        bool(state.get("_cloud_connected")),
        bool(state.get("_robot_online")),
        bool(state.get("_live_shadow_connected", False)),
        _recorder._stable_small(state.get("_cloud_error")),  # noqa: SLF001
        _recorder._stable_small(state.get("_live_shadow_error")),  # noqa: SLF001
        _recorder._sequence_edge_signature(state.get("_mowing_records")),  # noqa: SLF001
        _recorder._sequence_edge_signature(state.get("_task_events")),  # noqa: SLF001
        _actual_error_history_signature(state.get("_error_history")),
        _recorder._stable_small(state.get("robot_maintenance")),  # noqa: SLF001
        _recorder._stable_small(coordinator.last_mowing_task),  # noqa: SLF001
        bool(coordinator.custom_button_actions_configured),
        bool(coordinator.custom_button_actions_enabled),
        _recorder._stable_small(coordinator.custom_button_actions),  # noqa: SLF001
    )


def install_recorder_idle_semantics_v2467() -> None:
    """Replace only the semantic classifier used by the installed write filter."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _recorder._map_live_signature = _stable_map_live_signature  # noqa: SLF001
