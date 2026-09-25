"""Low-risk CPU hot-path fixes for issue #64.

Keeps telemetry cadence and mower behavior unchanged.  It removes duplicate
recursive history walks and adds cheap bounding-box rejection before the exact
no-go geometry checks.
"""

from __future__ import annotations

from typing import Any

from .. import coordinator as coordinator_module
from .. import path_zone_check
from . import genie_path_diagnostics, m_series_path

_INSTALLED = False


def _walk_history_once(value: Any) -> tuple[Any, str | None]:
    """Find history metadata and URL in one linear traversal.

    The old URL walker recursed into history-info children in its first loop and
    then recursed into every child again in a second loop. Nested history
    payloads therefore caused the same subtrees to be visited repeatedly.
    """
    info = None
    url = None
    stack = [value]
    seen: set[int] = set()

    while stack and (info is None or url is None):
        current = stack.pop()
        if isinstance(current, dict):
            object_id = id(current)
            if object_id in seen:
                continue
            seen.add(object_id)

            for key, item in current.items():
                if info is None and key in coordinator_module._HISTORY_INFO_KEYS:
                    info = item
                if (
                    url is None
                    and key in coordinator_module._HISTORY_PATH_URL_KEYS
                    and isinstance(item, str)
                    and item.startswith(("http://", "https://"))
                ):
                    url = item
            for item in reversed(tuple(current.values())):
                if isinstance(item, (dict, list)):
                    stack.append(item)
                elif (
                    url is None
                    and isinstance(item, str)
                    and item.startswith(("http://", "https://"))
                    and any(part in item.lower() for part in ("path", "history", "record"))
                ):
                    url = item
        elif isinstance(current, list):
            object_id = id(current)
            if object_id in seen:
                continue
            seen.add(object_id)
            for item in reversed(current):
                if isinstance(item, (dict, list)):
                    stack.append(item)
                elif (
                    url is None
                    and isinstance(item, str)
                    and item.startswith(("http://", "https://"))
                    and any(part in item.lower() for part in ("path", "history", "record"))
                ):
                    url = item
        elif (
            url is None
            and isinstance(current, str)
            and current.startswith(("http://", "https://"))
            and any(part in current.lower() for part in ("path", "history", "record"))
        ):
            url = current
    return info, url


def _find_history_info(*values: Any) -> Any:
    for value in values:
        info, _ = _walk_history_once(value)
        if info is not None:
            return info
    return None


def _find_history_url(*values: Any) -> str | None:
    for value in values:
        _, url = _walk_history_once(value)
        if url:
            return url
    return None


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _outside(point: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    return point[0] < box[0] or point[0] > box[2] or point[1] < box[1] or point[1] > box[3]


def _segment_misses_box(first: tuple[float, float], second: tuple[float, float], box: tuple[float, float, float, float]) -> bool:
    return (
        max(first[0], second[0]) < box[0]
        or min(first[0], second[0]) > box[2]
        or max(first[1], second[1]) < box[1]
        or min(first[1], second[1]) > box[3]
    )


def _evaluate_path_no_go(path_points: Any, data: dict[str, Any], *, path_id: Any = None) -> dict[str, Any]:
    """Equivalent no-go diagnostics with bbox rejection before exact geometry."""
    zones = path_zone_check.no_go_zones(data)
    runs = path_zone_check._path_runs(path_points)
    valid_point_count = sum(len(run) for run in runs)
    segment_count = sum(max(0, len(run) - 1) for run in runs)
    inside_path_indices: set[int] = set()
    boundary_crossings = 0
    traversals = 0
    affected_zone_ids: list[Any] = []
    zone_results: list[dict[str, Any]] = []
    last_crossing = None

    for zone_index, zone in enumerate(zones):
        polygon = zone["points"]
        box = _bbox(polygon)
        zone_inside_indices: set[int] = set()
        zone_crossings = 0
        zone_traversals = 0
        zone_last_crossing = None

        for run in runs:
            if not run:
                continue
            start_inside = False if _outside(run[0][1], box) else path_zone_check.point_in_polygon(run[0][1], polygon)
            end_inside = False if _outside(run[-1][1], box) else path_zone_check.point_in_polygon(run[-1][1], polygon)
            for point_index, point in run:
                if not _outside(point, box) and path_zone_check.point_in_polygon(point, polygon):
                    zone_inside_indices.add(point_index)
                    inside_path_indices.add(point_index)

            run_crossings = 0
            for segment_index in range(len(run) - 1):
                path_index, first = run[segment_index]
                _, second = run[segment_index + 1]
                if _segment_misses_box(first, second, box):
                    continue
                intersections = path_zone_check._segment_polygon_intersections(first, second, polygon)
                run_crossings += len(intersections)
                zone_crossings += len(intersections)
                boundary_crossings += len(intersections)
                for t, crossing in intersections:
                    crossing_info = {
                        "x": crossing[0], "y": crossing[1],
                        "zone_id": zone.get("id"), "zone_name": zone.get("name"),
                        "path_segment_start_index": path_index, "segment_t": t,
                    }
                    zone_last_crossing = crossing_info
                    last_crossing = crossing_info
            zone_traversals += (run_crossings + int(start_inside) + int(end_inside)) // 2

        affected = bool(zone_inside_indices or zone_crossings)
        zone_id = zone.get("id")
        if affected:
            affected_zone_ids.append(zone_id if zone_id is not None else f"index:{zone_index}")
        traversals += zone_traversals
        zone_results.append({
            "zone_id": zone_id, "zone_name": zone.get("name"), "source_key": zone.get("source_key"),
            "points_inside": len(zone_inside_indices), "boundary_crossings": zone_crossings,
            "traversals": zone_traversals, "last_crossing": zone_last_crossing,
        })

    return {
        "source": "m_series_assembled_path", "path_id": path_id,
        "crossing_detected": bool(inside_path_indices or boundary_crossings),
        "checked_point_count": valid_point_count, "checked_segment_count": segment_count,
        "no_go_zone_count": len(zones), "points_inside": len(inside_path_indices),
        "boundary_crossings": boundary_crossings, "traversals": traversals,
        "zone_ids": affected_zone_ids, "last_crossing": last_crossing, "zones": zone_results,
    }


def install_issue64_cpu_hotpath_fix() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # Both the periodic coordinator and Genie live-path layer resolve these
    # module globals at runtime, so one patch covers both call paths.
    coordinator_module._find_history_info = _find_history_info
    coordinator_module._find_history_path_url = _find_history_url
    coordinator_module._walk_for_history_info = lambda value: _walk_history_once(value)[0]
    coordinator_module._walk_for_history_url = lambda value: _walk_history_once(value)[1]

    # These model modules imported evaluate_path_no_go by value; replace their
    # local references explicitly without touching telemetry or command logic.
    genie_path_diagnostics.evaluate_path_no_go = _evaluate_path_no_go
    m_series_path.evaluate_path_no_go = _evaluate_path_no_go
