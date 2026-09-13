"""Pure live-map stream delta builder for ANTHBOT Map.

This module intentionally has no Home Assistant imports so the protocol and
rolling-path logic can be regression-tested without a Home Assistant runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 2


def _mapping_point_signature(value: Any) -> tuple[Any, ...] | Any:
    """Return a cheap stable signature for a path/pose mapping."""
    if not isinstance(value, dict):
        return value
    keys = ("x", "y", "z", "yaw", "heading", "angle", "type", "clean_time")
    return tuple((key, value.get(key)) for key in keys if key in value)


def _path_definition(state: dict[str, Any]) -> dict[str, Any]:
    value = state.get("_path_definition")
    return value if isinstance(value, dict) else {}


def _path_points(state: dict[str, Any]) -> list[dict[str, Any]]:
    definition = _path_definition(state)
    value = definition.get("_path_points")
    if not isinstance(value, list):
        value = state.get("path")
    if not isinstance(value, list):
        return []
    # Do not copy the assembled list on every coordinator update. Decoders in
    # this integration produce mapping points; individual values are still
    # validated by the signature helper when continuity is checked.
    return value


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def _absolute_path_bounds(
    definition: dict[str, Any], point_count: int
) -> tuple[int | None, int | None]:
    """Return verified assembled absolute path indices when available."""
    first = _coerce_int(definition.get("_m_series_first_index"))
    last = _coerce_int(definition.get("_m_series_last_index"))
    if first is None or last is None or last < first:
        return None, None
    if point_count == 0:
        return first, last
    if last - first + 1 != point_count:
        # Never use ``start`` as a substitute here: on N8/M-series it is the
        # start of the latest chunk, not necessarily the assembled window.
        return None, None
    return first, last


def _path_identity(state: dict[str, Any], definition: dict[str, Any]) -> Any:
    path_id = definition.get("path_id")
    if path_id not in (None, ""):
        return path_id
    history = state.get("_history_path_info")
    if isinstance(history, dict):
        path_id = history.get("path_id")
        if path_id not in (None, ""):
            return path_id
    return None


def _path_metadata(definition: dict[str, Any], points: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "path_id",
        "start",
        "task_type",
        "point_count",
        "coordinate_scale",
        "format",
        "protocol_version",
    ):
        value = definition.get(key)
        if value is not None:
            result[key] = value
    # The decoder metadata may describe only the latest wire chunk. The live
    # stream exposes the assembled path length instead.
    result["point_count"] = len(points)
    return result


def _definition_status(value: Any) -> str:
    if isinstance(value, dict):
        return f"dict:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if value is None:
        return "not_loaded"
    return type(value).__name__


def _binary_paths(value: Any) -> list[dict[str, Any]]:
    """Return the same compact coordinate-path shape used by the Map entity."""
    if not isinstance(value, dict):
        return []
    probe = value.get("_binary_probe")
    if not isinstance(probe, dict):
        return []
    paths = probe.get("coordinate_paths")
    if not isinstance(paths, list):
        return []
    compact: list[dict[str, Any]] = []
    for path in paths[:4]:
        if not isinstance(path, dict):
            continue
        points = path.get("points")
        if not isinstance(points, list) or len(points) < 3:
            continue
        compact.append(
            {
                "encoding": path.get("encoding"),
                "offset": path.get("offset"),
                "count": path.get("count"),
                "bounds": path.get("bounds"),
                "points": points,
            }
        )
    return compact


def _ridable_areas(state: dict[str, Any]) -> list[dict[str, Any]]:
    def list_of_dicts(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    separate = state.get("_ridable_area_definition")
    if isinstance(separate, list):
        edges = list_of_dicts(separate)
        if edges:
            return edges
    if isinstance(separate, dict):
        for key in ("ridable_areas", "ridableAreas", "areas", "data"):
            edges = list_of_dicts(separate.get(key))
            if edges:
                return edges
    area = state.get("_area_definition")
    if isinstance(area, dict):
        for key in ("ridable_areas", "ridableAreas"):
            edges = list_of_dicts(area.get(key))
            if edges:
                return edges
    return list_of_dicts(state.get("ridable_areas"))


def _map_revision(state: dict[str, Any]) -> tuple[Any, ...]:
    definition = state.get("_map_definition")
    raster = definition.get("_map_raster") if isinstance(definition, dict) else None
    return (
        # map_time is deliberately excluded: field data shows it can rotate
        # while the actual map geometry is unchanged.
        definition.get("map_id") if isinstance(definition, dict) else None,
        definition.get("_download_source") if isinstance(definition, dict) else None,
        raster.get("encoding") if isinstance(raster, dict) else None,
        raster.get("width") if isinstance(raster, dict) else None,
        raster.get("height") if isinstance(raster, dict) else None,
        raster.get("bounds") if isinstance(raster, dict) else None,
    )


def _area_revision(state: dict[str, Any]) -> tuple[Any, ...]:
    area = state.get("_area_definition")
    ridable = state.get("_ridable_area_definition")

    def collection_shape(value: Any) -> tuple[Any, ...]:
        if not isinstance(value, dict):
            if isinstance(value, list):
                return ("list", len(value))
            return (type(value).__name__,)
        result: list[tuple[str, int]] = []
        for key in (
            "custom_areas",
            "zones",
            "customAreas",
            "region_areas",
            "auto_zones",
            "forbid_areas",
            "no_go_areas",
            "ridable_areas",
            "ridableAreas",
            "areas",
            "data",
        ):
            child = value.get(key)
            if isinstance(child, list):
                result.append((key, len(child)))
        return tuple(result)

    return (
        state.get("area_time"),
        state.get("ridable_area_time"),
        collection_shape(area),
        collection_shape(ridable),
    )


def _history_revision(state: dict[str, Any]) -> tuple[Any, ...]:
    info = state.get("_history_path_info")
    if isinstance(info, dict):
        info_sig = tuple((key, info.get(key)) for key in ("map_id", "path_id", "time"))
    else:
        info_sig = (info,)
    return (
        info_sig,
        state.get("_history_path_source"),
        state.get("_history_path_live_refresh"),
        state.get("_history_path_refresh_interval"),
    )


def _pose_revision(state: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _mapping_point_signature(state.get("pose")),
        _mapping_point_signature(state.get("curPose") or state.get("cur_pose")),
        _mapping_point_signature(state.get("mapScanPose") or state.get("map_scan_pose")),
    )


def _snapshot_attributes(state: dict[str, Any]) -> dict[str, Any]:
    map_definition = state.get("_map_definition")
    path_definition = _path_definition(state)
    raster = map_definition.get("_map_raster") if isinstance(map_definition, dict) else None
    return {
        "pose": state.get("pose"),
        "cur_pose": state.get("curPose") or state.get("cur_pose"),
        "map_scan_pose": state.get("mapScanPose") or state.get("map_scan_pose"),
        "map_time": state.get("map_time"),
        "path_time": state.get("path_time"),
        "area_time": state.get("area_time"),
        "ridable_area_time": state.get("ridable_area_time"),
        "history_path_info": state.get("_history_path_info"),
        "history_path_source": state.get("_history_path_source"),
        "history_path_live_refresh": state.get("_history_path_live_refresh"),
        "history_path_refresh_interval": state.get("_history_path_refresh_interval"),
        "history_path_download_source": path_definition.get("_download_source"),
        "area_definition": state.get("_area_definition") or {},
        "ridable_areas": _ridable_areas(state),
        "ridable_area_error": state.get("_ridable_area_definition_error"),
        "map_definition_status": _definition_status(map_definition),
        "path_definition_status": _definition_status(path_definition),
        "map_raster": raster if isinstance(raster, dict) else None,
        "map_binary_paths": _binary_paths(map_definition),
        "path_binary_paths": _binary_paths(path_definition),
        "map_definition_error": state.get("_map_definition_error"),
        "path_definition_error": state.get("_path_definition_error"),
    }


def _delta_attributes(previous: "LiveMapCursor", state: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    pose_revision = _pose_revision(state)
    if pose_revision != previous.pose_revision:
        result["pose"] = state.get("pose")
        result["cur_pose"] = state.get("curPose") or state.get("cur_pose")
        result["map_scan_pose"] = state.get("mapScanPose") or state.get("map_scan_pose")

    # path_time is cheap and useful for card diagnostics, but does not force a
    # full path payload. It travels independently from the path append/reset.
    if state.get("path_time") != previous.path_time:
        result["path_time"] = state.get("path_time")

    map_revision = _map_revision(state)
    if map_revision != previous.map_revision:
        map_definition = state.get("_map_definition")
        raster = map_definition.get("_map_raster") if isinstance(map_definition, dict) else None
        result.update(
            {
                "map_time": state.get("map_time"),
                "map_definition_status": _definition_status(map_definition),
                "map_raster": raster if isinstance(raster, dict) else None,
                "map_binary_paths": _binary_paths(map_definition),
                "map_definition_error": state.get("_map_definition_error"),
            }
        )

    area_revision = _area_revision(state)
    if area_revision != previous.area_revision:
        result.update(
            {
                "area_time": state.get("area_time"),
                "ridable_area_time": state.get("ridable_area_time"),
                "area_definition": state.get("_area_definition") or {},
                "ridable_areas": _ridable_areas(state),
                "ridable_area_error": state.get("_ridable_area_definition_error"),
            }
        )

    history_revision = _history_revision(state)
    if history_revision != previous.history_revision:
        result.update(
            {
                "history_path_info": state.get("_history_path_info"),
                "history_path_source": state.get("_history_path_source"),
                "history_path_live_refresh": state.get("_history_path_live_refresh"),
                "history_path_refresh_interval": state.get("_history_path_refresh_interval"),
            }
        )

    current_path_error = state.get("_path_definition_error")
    if current_path_error != previous.path_definition_error:
        result["path_definition_error"] = current_path_error
    return result


@dataclass(frozen=True)
class LiveMapCursor:
    """Small client-independent cursor for incremental map delivery."""

    path_id: Any
    path_length: int
    path_first_index: int | None
    path_last_index: int | None
    path_last_signature: Any
    pose_revision: tuple[Any, ...]
    path_time: Any
    map_revision: tuple[Any, ...]
    area_revision: tuple[Any, ...]
    history_revision: tuple[Any, ...]
    path_definition_error: Any

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> "LiveMapCursor":
        definition = _path_definition(state)
        points = _path_points(state)
        first, last = _absolute_path_bounds(definition, len(points))
        return cls(
            path_id=_path_identity(state, definition),
            path_length=len(points),
            path_first_index=first,
            path_last_index=last,
            path_last_signature=(
                _mapping_point_signature(points[-1]) if points else None
            ),
            pose_revision=_pose_revision(state),
            path_time=state.get("path_time"),
            map_revision=_map_revision(state),
            area_revision=_area_revision(state),
            history_revision=_history_revision(state),
            path_definition_error=state.get("_path_definition_error"),
        )


def _reset_path_payload(state: dict[str, Any]) -> dict[str, Any]:
    definition = _path_definition(state)
    points = _path_points(state)
    first, last = _absolute_path_bounds(definition, len(points))
    return {
        "op": "reset",
        "path_id": _path_identity(state, definition),
        "start_index": first,
        "end_index": last,
        "metadata": _path_metadata(definition, points),
        "points": points,
    }


def _path_delta(previous: LiveMapCursor, state: dict[str, Any]) -> dict[str, Any] | None:
    definition = _path_definition(state)
    points = _path_points(state)
    path_id = _path_identity(state, definition)
    first, last = _absolute_path_bounds(definition, len(points))

    if path_id != previous.path_id:
        return _reset_path_payload(state)

    if not points and previous.path_length:
        return _reset_path_payload(state)
    if not points:
        return None

    metadata = _path_metadata(definition, points)

    # Preferred M-series/N8 path: absolute assembled indices let us trim a
    # rolling 20k window and append only genuinely new points.
    if (
        first is not None
        and last is not None
        and previous.path_first_index is not None
        and previous.path_last_index is not None
    ):
        previous_last = previous.path_last_index
        if last < previous_last or first > previous_last + 1:
            return _reset_path_payload(state)

        if first <= previous_last <= last:
            overlap_offset = previous_last - first
            if not 0 <= overlap_offset < len(points):
                return _reset_path_payload(state)
            if _mapping_point_signature(points[overlap_offset]) != previous.path_last_signature:
                return _reset_path_payload(state)
            append_offset = overlap_offset + 1
        elif first == previous_last + 1:
            append_offset = 0
        else:
            return _reset_path_payload(state)

        appended = points[append_offset:]
        trim_before = first if first > previous.path_first_index else None
        if not appended and trim_before is None:
            return None
        return {
            "op": "append",
            "path_id": path_id,
            "window_start_index": first,
            "append_from_index": first + append_offset,
            "end_index": last,
            "trim_before_index": trim_before,
            "metadata": metadata,
            "points": appended,
        }

    # Generic/Genie fallback: when no absolute indices exist, validate the
    # previous tail in-place and append from the old length. Any shrink or
    # rewritten tail becomes a reset rather than risking a corrupt trajectory.
    if len(points) < previous.path_length:
        return _reset_path_payload(state)
    if previous.path_length:
        anchor_offset = previous.path_length - 1
        if anchor_offset >= len(points):
            return _reset_path_payload(state)
        if _mapping_point_signature(points[anchor_offset]) != previous.path_last_signature:
            return _reset_path_payload(state)
    appended = points[previous.path_length:]
    if not appended:
        return None
    return {
        "op": "append",
        "path_id": path_id,
        "window_start_index": None,
        "append_from_index": previous.path_length,
        "end_index": None,
        "trim_before_index": None,
        "metadata": metadata,
        "points": appended,
    }


def build_snapshot(
    serial_number: str,
    sequence: int,
    state: dict[str, Any],
) -> tuple[dict[str, Any], LiveMapCursor]:
    """Build a complete first frame for a newly subscribed card."""
    cursor = LiveMapCursor.from_state(state)
    payload = {
        "protocol": PROTOCOL_VERSION,
        "kind": "snapshot",
        "sequence": sequence,
        "serial_number": serial_number,
        "attributes": _snapshot_attributes(state),
        "path": _reset_path_payload(state),
    }
    return payload, cursor


def build_delta(
    serial_number: str,
    sequence: int,
    previous: LiveMapCursor,
    state: dict[str, Any],
) -> tuple[dict[str, Any] | None, LiveMapCursor]:
    """Build an incremental frame, or None when nothing visual changed."""
    current = LiveMapCursor.from_state(state)
    attributes = _delta_attributes(previous, state)
    path = _path_delta(previous, state)
    if not attributes and path is None:
        return None, current
    payload: dict[str, Any] = {
        "protocol": PROTOCOL_VERSION,
        "kind": "delta",
        "sequence": sequence,
        "serial_number": serial_number,
        "attributes": attributes,
    }
    if path is not None:
        payload["path"] = path
    return payload, current
