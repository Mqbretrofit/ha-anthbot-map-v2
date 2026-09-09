"""No-go-zone diagnostics for assembled mower paths.

This module is intentionally read-only: it never changes, filters or rejects
telemetry. It only measures whether an already assembled mower trajectory
enters or crosses configured no-go polygons.
"""

from __future__ import annotations

import math
from typing import Any

_NO_GO_KEYS = (
    "forbid_areas",
    "forbidAreas",
    "remote_forbid_areas",
    "remoteForbidAreas",
    "no_go_areas",
    "noGoAreas",
)
_POINT_KEYS = ("vertexs", "vertices", "points", "path", "polygon")
_EPSILON = 1e-9


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _polygon_points(value: Any) -> list[tuple[float, float]]:
    candidate = value
    if isinstance(value, dict):
        candidate = None
        for key in _POINT_KEYS:
            points = value.get(key)
            if isinstance(points, (list, tuple)) and points:
                candidate = points
                break
    if not isinstance(candidate, (list, tuple)) or not candidate:
        return []

    points: list[tuple[float, float]] = []
    if all(isinstance(item, (int, float, str)) for item in candidate):
        if len(candidate) % 2:
            return []
        for index in range(0, len(candidate), 2):
            x = _finite_float(candidate[index])
            y = _finite_float(candidate[index + 1])
            if x is not None and y is not None:
                points.append((x, y))
        return points

    for item in candidate:
        if isinstance(item, dict):
            x = _finite_float(item.get("x"))
            y = _finite_float(item.get("y"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x = _finite_float(item[0])
            y = _finite_float(item[1])
        else:
            continue
        if x is not None and y is not None:
            points.append((x, y))
    return points


def _find_area_definition(data: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("_area_definition", "area_definition"):
        direct = data.get(key)
        if isinstance(direct, dict):
            return direct

    stack: list[tuple[Any, int]] = [(data, 0)]
    seen: set[int] = set()
    while stack:
        current, depth = stack.pop()
        if not isinstance(current, dict):
            continue
        object_id = id(current)
        if object_id in seen:
            continue
        seen.add(object_id)
        if any(key in current for key in _NO_GO_KEYS):
            return current
        if depth >= 5:
            continue
        for child in current.values():
            if isinstance(child, dict):
                stack.append((child, depth + 1))
    return None


def no_go_zones(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized no-go zones from all known ANTHBOT payload keys."""
    definition = _find_area_definition(data)
    if not isinstance(definition, dict):
        return []

    zones: list[dict[str, Any]] = []
    signatures: set[tuple[Any, tuple[tuple[float, float], ...]]] = set()
    for key in _NO_GO_KEYS:
        raw_zones = definition.get(key)
        if not isinstance(raw_zones, (list, tuple)):
            continue
        for index, raw_zone in enumerate(raw_zones):
            if isinstance(raw_zone, dict):
                zone = raw_zone
            elif isinstance(raw_zone, (list, tuple)):
                zone = {"points": raw_zone}
            else:
                continue
            points = _polygon_points(zone)
            if len(points) < 3:
                continue
            zone_id = zone.get("id")
            signature = (zone_id if zone_id is not None else (key, index), tuple(points))
            if signature in signatures:
                continue
            signatures.add(signature)
            zones.append(
                {
                    "id": zone_id,
                    "name": zone.get("name"),
                    "source_key": key,
                    "points": points,
                }
            )
    return zones


def no_go_geometry_signature(data: dict[str, Any]) -> tuple[Any, ...]:
    """Return a stable, compact signature for no-go geometry cache invalidation."""
    return tuple(
        (
            zone.get("id"),
            zone.get("name"),
            zone.get("source_key"),
            tuple(zone.get("points", ())),
        )
        for zone in no_go_zones(data)
    )


def _point_on_segment(
    point: tuple[float, float],
    first: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    px, py = point
    ax, ay = first
    bx, by = second
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    scale = max(1.0, abs(bx - ax), abs(by - ay))
    if abs(cross) > _EPSILON * scale:
        return False
    return (
        min(ax, bx) - _EPSILON <= px <= max(ax, bx) + _EPSILON
        and min(ay, by) - _EPSILON <= py <= max(ay, by) + _EPSILON
    )


def point_in_polygon(
    point: tuple[float, float], polygon: list[tuple[float, float]]
) -> bool:
    """Return whether point is inside or on the boundary of polygon."""
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if _point_on_segment(point, previous, current):
            return True
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def _segment_intersection_t(
    first: tuple[float, float],
    second: tuple[float, float],
    edge_first: tuple[float, float],
    edge_second: tuple[float, float],
) -> float | None:
    ax, ay = first
    bx, by = second
    cx, cy = edge_first
    dx, dy = edge_second
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    denominator = rx * sy - ry * sx
    if abs(denominator) <= _EPSILON:
        # Collinear travel along a boundary is not an entry/exit crossing.
        return None
    qx, qy = cx - ax, cy - ay
    t = (qx * sy - qy * sx) / denominator
    u = (qx * ry - qy * rx) / denominator
    if -_EPSILON <= t <= 1.0 + _EPSILON and -_EPSILON <= u <= 1.0 + _EPSILON:
        return min(1.0, max(0.0, t))
    return None


def _segment_polygon_intersections(
    first: tuple[float, float],
    second: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> list[tuple[float, tuple[float, float]]]:
    values: list[tuple[float, tuple[float, float]]] = []
    previous = polygon[-1]
    for current in polygon:
        t = _segment_intersection_t(first, second, previous, current)
        if t is not None:
            x = first[0] + (second[0] - first[0]) * t
            y = first[1] + (second[1] - first[1]) * t
            if not any(abs(t - old_t) <= 1e-7 for old_t, _ in values):
                values.append((t, (x, y)))
        previous = current
    values.sort(key=lambda item: item[0])
    return values


def _path_runs(path_points: Any) -> list[list[tuple[int, tuple[float, float]]]]:
    if not isinstance(path_points, list):
        return []
    runs: list[list[tuple[int, tuple[float, float]]]] = []
    current: list[tuple[int, tuple[float, float]]] = []
    for index, raw in enumerate(path_points):
        if not isinstance(raw, dict):
            if current:
                runs.append(current)
                current = []
            continue
        x = _finite_float(raw.get("x"))
        y = _finite_float(raw.get("y"))
        if x is None or y is None:
            if current:
                runs.append(current)
                current = []
            continue
        if raw.get("break_before") is True and current:
            runs.append(current)
            current = []
        current.append((index, (x, y)))
    if current:
        runs.append(current)
    return runs


def evaluate_path_no_go(
    path_points: Any,
    data: dict[str, Any],
    *,
    path_id: Any = None,
) -> dict[str, Any]:
    """Measure no-go crossings without modifying the supplied trajectory."""
    zones = no_go_zones(data)
    runs = _path_runs(path_points)
    valid_point_count = sum(len(run) for run in runs)
    segment_count = sum(max(0, len(run) - 1) for run in runs)

    inside_path_indices: set[int] = set()
    boundary_crossings = 0
    traversals = 0
    affected_zone_ids: list[Any] = []
    zone_results: list[dict[str, Any]] = []
    last_crossing: dict[str, Any] | None = None

    for zone_index, zone in enumerate(zones):
        polygon = zone["points"]
        zone_inside_indices: set[int] = set()
        zone_crossings = 0
        zone_traversals = 0
        zone_last_crossing: dict[str, Any] | None = None

        for run in runs:
            if not run:
                continue
            start_inside = point_in_polygon(run[0][1], polygon)
            end_inside = point_in_polygon(run[-1][1], polygon)
            for point_index, point in run:
                if point_in_polygon(point, polygon):
                    zone_inside_indices.add(point_index)
                    inside_path_indices.add(point_index)

            run_crossings = 0
            for segment_index in range(len(run) - 1):
                path_index, first = run[segment_index]
                _, second = run[segment_index + 1]
                intersections = _segment_polygon_intersections(first, second, polygon)
                run_crossings += len(intersections)
                zone_crossings += len(intersections)
                boundary_crossings += len(intersections)
                for t, crossing in intersections:
                    crossing_info = {
                        "x": crossing[0],
                        "y": crossing[1],
                        "zone_id": zone.get("id"),
                        "zone_name": zone.get("name"),
                        "path_segment_start_index": path_index,
                        "segment_t": t,
                    }
                    zone_last_crossing = crossing_info
                    last_crossing = crossing_info

            # Number of inside trajectory intervals in this continuous run.
            # This handles outside->outside crossings (2 => 1 traversal),
            # outside->inside / inside->outside (1 => 1), paths starting or
            # ending inside, and paths entirely inside (0 + 1 + 1 => 1).
            zone_traversals += (
                run_crossings + int(start_inside) + int(end_inside)
            ) // 2

        affected = bool(zone_inside_indices or zone_crossings)
        zone_id = zone.get("id")
        if affected:
            identifier = zone_id if zone_id is not None else f"index:{zone_index}"
            affected_zone_ids.append(identifier)
        traversals += zone_traversals
        zone_results.append(
            {
                "zone_id": zone_id,
                "zone_name": zone.get("name"),
                "source_key": zone.get("source_key"),
                "points_inside": len(zone_inside_indices),
                "boundary_crossings": zone_crossings,
                "traversals": zone_traversals,
                "last_crossing": zone_last_crossing,
            }
        )

    crossing_detected = bool(inside_path_indices or boundary_crossings)
    return {
        "source": "m_series_assembled_path",
        "path_id": path_id,
        "crossing_detected": crossing_detected,
        "checked_point_count": valid_point_count,
        "checked_segment_count": segment_count,
        "no_go_zone_count": len(zones),
        "points_inside": len(inside_path_indices),
        "boundary_crossings": boundary_crossings,
        "traversals": traversals,
        "zone_ids": affected_zone_ids,
        "last_crossing": last_crossing,
        "zones": zone_results,
    }
