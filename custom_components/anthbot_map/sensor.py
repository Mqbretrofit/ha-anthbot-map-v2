"""Sensor platform for Anthbot Genie."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfArea,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ERROR_CODE_DESCRIPTIONS,
    RTK_BASE_STATE_OPTIONS,
    RTK_STATE_OPTIONS,
)
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .task_events import (
    latest_task_event,
    task_event_code,
    task_event_datetime,
    task_event_items,
    task_event_value,
)
from .zones import active_manual_zone_ids, auto_zones, manual_zones, ridable_areas


def _safe_get(data: dict[str, Any], *path: str) -> Any:
    """Walk a nested dict path, returning None if any hop is missing."""
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def _battery_level(data: dict[str, Any]) -> int | None:
    """Return a validated battery percentage for all known payload formats."""
    raw_value = data.get("elec")
    seen_wrappers: set[int] = set()
    while isinstance(raw_value, dict):
        wrapper_id = id(raw_value)
        if wrapper_id in seen_wrappers:
            return None
        seen_wrappers.add(wrapper_id)
        raw_value = raw_value.get("value")

    value = _as_int(raw_value)
    if value is None or not 0 <= value <= 100:
        return None
    return value




# --- MOWING PROGRESS v2.4.3-beta.2 ---
def _progress_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _progress_zone_id(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _progress_zone_points(zone: dict[str, Any]) -> list[tuple[float, float]]:
    candidate = None
    for key in ("vertexs", "vertices", "points", "path", "polygon"):
        value = zone.get(key)
        if isinstance(value, (list, tuple)) and value:
            candidate = value
            break
    if candidate is None:
        return []

    points: list[tuple[float, float]] = []

    if all(isinstance(item, (int, float, str)) for item in candidate):
        if len(candidate) % 2:
            return []
        for idx in range(0, len(candidate), 2):
            x = _progress_float(candidate[idx])
            y = _progress_float(candidate[idx + 1])
            if x is not None and y is not None:
                points.append((x, y))
        return points

    for item in candidate:
        if isinstance(item, dict):
            x = _progress_float(item.get("x"))
            y = _progress_float(item.get("y"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x = _progress_float(item[0])
            y = _progress_float(item[1])
        else:
            continue
        if x is not None and y is not None:
            points.append((x, y))
    return points


def _progress_polygon_area_raw(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 3:
        return None
    area2 = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        area2 += x1 * y2 - x2 * y1
    area = abs(area2) / 2.0
    return area if area > 0 else None


def _progress_polygon_segments(
    points: list[tuple[float, float]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if len(points) < 2:
        return []
    result = []
    for idx, first in enumerate(points):
        second = points[(idx + 1) % len(points)]
        if first != second:
            result.append((first, second))
    return result


def _progress_segment_intersection_x(
    first: tuple[tuple[float, float], tuple[float, float]],
    second: tuple[tuple[float, float], tuple[float, float]],
) -> float | None:
    (ax, ay), (bx, by) = first
    (cx, cy), (dx, dy) = second
    rx = bx - ax
    ry = by - ay
    sx = dx - cx
    sy = dy - cy
    denominator = rx * sy - ry * sx
    if abs(denominator) < 1e-12:
        # Parallel/collinear segments can only change topology at their
        # endpoints, which are already included as sweep events.
        return None

    qx = cx - ax
    qy = cy - ay
    t = (qx * sy - qy * sx) / denominator
    u = (qx * ry - qy * rx) / denominator
    tolerance = 1e-9
    if not (-tolerance <= t <= 1.0 + tolerance):
        return None
    if not (-tolerance <= u <= 1.0 + tolerance):
        return None
    return ax + t * rx


def _progress_union_intervals_at_x(
    polygons: list[list[tuple[float, float]]],
    x_value: float,
) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    for points in polygons:
        y_values: list[float] = []
        for (x1, y1), (x2, y2) in _progress_polygon_segments(points):
            if abs(x2 - x1) < 1e-12:
                continue
            low_x = min(x1, x2)
            high_x = max(x1, x2)
            # x_value is always inside a sweep slab, never on a vertex event.
            if not (low_x < x_value < high_x):
                continue
            ratio = (x_value - x1) / (x2 - x1)
            y_values.append(y1 + ratio * (y2 - y1))

        y_values.sort()
        for idx in range(0, len(y_values) - 1, 2):
            low_y = y_values[idx]
            high_y = y_values[idx + 1]
            if high_y > low_y:
                intervals.append((low_y, high_y))

    intervals.sort()
    merged: list[list[float]] = []
    for low_y, high_y in intervals:
        if not merged or low_y > merged[-1][1] + 1e-9:
            merged.append([low_y, high_y])
        elif high_y > merged[-1][1]:
            merged[-1][1] = high_y
    return [(item[0], item[1]) for item in merged]


def _progress_interval_intersection_length(
    first: list[tuple[float, float]],
    second: list[tuple[float, float]],
) -> float:
    first_idx = 0
    second_idx = 0
    total = 0.0
    while first_idx < len(first) and second_idx < len(second):
        low_y = max(first[first_idx][0], second[second_idx][0])
        high_y = min(first[first_idx][1], second[second_idx][1])
        if high_y > low_y:
            total += high_y - low_y
        if first[first_idx][1] < second[second_idx][1]:
            first_idx += 1
        else:
            second_idx += 1
    return total


def _progress_polygon_union_intersection_area_raw(
    first_polygons: list[list[tuple[float, float]]],
    second_polygons: list[list[tuple[float, float]]],
) -> float:
    """Exact sweep-area of union(first) intersect union(second).

    This handles multiple overlapping No-Go polygons without subtracting the
    overlap twice and also handles No-Go polygons that cross a mowing-zone
    boundary. No external geometry package is required.
    """
    first_polygons = [points for points in first_polygons if len(points) >= 3]
    second_polygons = [points for points in second_polygons if len(points) >= 3]
    if not first_polygons or not second_polygons:
        return 0.0

    first_x = [point[0] for points in first_polygons for point in points]
    first_y = [point[1] for points in first_polygons for point in points]
    second_x = [point[0] for points in second_polygons for point in points]
    second_y = [point[1] for points in second_polygons for point in points]
    if (
        max(first_x) <= min(second_x)
        or max(second_x) <= min(first_x)
        or max(first_y) <= min(second_y)
        or max(second_y) <= min(first_y)
    ):
        return 0.0

    events: list[float] = []
    tagged_segments: list[
        tuple[int, int, tuple[tuple[float, float], tuple[float, float]]]
    ] = []

    for set_index, polygons in enumerate((first_polygons, second_polygons)):
        for polygon_index, points in enumerate(polygons):
            events.extend(point[0] for point in points)
            for segment in _progress_polygon_segments(points):
                tagged_segments.append((set_index, polygon_index, segment))

    # Boundary crossings are additional x-events. Between two consecutive
    # events the vertical coverage length is linear, so midpoint integration
    # is exact for that slab.
    for first_idx in range(len(tagged_segments)):
        first_set, first_polygon, first_segment = tagged_segments[first_idx]
        for second_idx in range(first_idx + 1, len(tagged_segments)):
            second_set, second_polygon, second_segment = tagged_segments[second_idx]
            if first_set == second_set and first_polygon == second_polygon:
                continue
            x_value = _progress_segment_intersection_x(first_segment, second_segment)
            if x_value is not None:
                events.append(x_value)

    events.sort()
    unique_events: list[float] = []
    for value in events:
        if not unique_events or abs(value - unique_events[-1]) > 1e-7:
            unique_events.append(value)

    total_area = 0.0
    for low_x, high_x in zip(unique_events, unique_events[1:]):
        width = high_x - low_x
        if width <= 1e-9:
            continue
        mid_x = (low_x + high_x) / 2.0
        first_intervals = _progress_union_intervals_at_x(first_polygons, mid_x)
        second_intervals = _progress_union_intervals_at_x(second_polygons, mid_x)
        overlap_height = _progress_interval_intersection_length(
            first_intervals, second_intervals
        )
        total_area += overlap_height * width

    return max(0.0, total_area)


_PROGRESS_EXPLICIT_AREA_KEYS = (
    "area_m2",
    "area",
    "area_size",
    "zone_area",
    "mow_area",
    "region_area",
    "size",
)


_PROGRESS_NO_GO_KEYS = (
    "forbid_areas",
    "forbidAreas",
    "remote_forbid_areas",
    "remoteForbidAreas",
    "no_go_areas",
    "noGoAreas",
)


def _progress_explicit_zone_area(zone: dict[str, Any]) -> tuple[float | None, str | None]:
    for key in _PROGRESS_EXPLICIT_AREA_KEYS:
        value = _progress_float(zone.get(key))
        if value is not None and value > 0:
            return value, key
    return None, None


def _progress_area_definition(data: dict[str, Any]) -> dict[str, Any] | None:
    direct = data.get("area_definition")
    if isinstance(direct, dict):
        return direct

    # The coordinator shape has changed between integration versions. Find
    # the area-definition object without depending on one exact nesting path.
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

        if any(
            key in current
            for key in (
                "custom_areas",
                "customAreas",
                "forbid_areas",
                "remote_forbid_areas",
                "no_go_areas",
            )
        ):
            return current

        if depth >= 5:
            continue
        for value in current.values():
            if isinstance(value, dict):
                stack.append((value, depth + 1))
    return None


def _progress_no_go_zones(data: dict[str, Any]) -> list[dict[str, Any]]:
    area_definition = _progress_area_definition(data)
    if not isinstance(area_definition, dict):
        return []

    result: list[dict[str, Any]] = []
    signatures: set[tuple[Any, tuple[tuple[float, float], ...]]] = set()
    for key in _PROGRESS_NO_GO_KEYS:
        value = area_definition.get(key)
        if not isinstance(value, (list, tuple)):
            continue
        for zone in value:
            if not isinstance(zone, dict):
                continue
            points = _progress_zone_points(zone)
            if len(points) < 3:
                continue
            signature = (_progress_zone_id(zone.get("id")), tuple(points))
            if signature in signatures:
                continue
            signatures.add(signature)
            result.append(zone)
    return result


def _progress_all_zone_polygon_raw(data: dict[str, Any]) -> tuple[float | None, int, int]:
    zones = list(manual_zones(data))
    if not zones:
        return None, 0, 0

    total = 0.0
    valid = 0
    for zone in zones:
        raw_area = _progress_polygon_area_raw(_progress_zone_points(zone))
        if raw_area is None:
            # A partial denominator would make the calibration misleading.
            return None, valid, len(zones)
        total += raw_area
        valid += 1

    return (total if total > 0 else None), valid, len(zones)


def _progress_active_zone_debug(data: dict[str, Any]) -> dict[str, Any]:
    active_ids = active_manual_zone_ids(data)
    id_set = set(active_ids)
    all_zones = list(manual_zones(data))
    selected = [
        zone
        for zone in all_zones
        if _progress_zone_id(zone.get("id")) in id_set
    ]

    map_area = _progress_float(data.get("map_area"))
    all_raw, all_raw_valid_count, all_zone_count = _progress_all_zone_polygon_raw(data)
    polygon_scale = None
    if (
        all_raw is not None
        and all_raw > 0
        and map_area is not None
        and map_area > 0
    ):
        polygon_scale = map_area / all_raw

    no_go_zones = _progress_no_go_zones(data)
    no_go_polygons = [_progress_zone_points(zone) for zone in no_go_zones]
    no_go_polygons = [points for points in no_go_polygons if len(points) >= 3]

    explicit_total = 0.0
    explicit_complete = bool(selected)
    raw_total = 0.0
    raw_complete = bool(selected)
    selected_polygons: list[list[tuple[float, float]]] = []
    selected_zone_no_go_overlaps: list[float] = []
    zones_debug: list[dict[str, Any]] = []

    for zone in selected:
        zone_id = _progress_zone_id(zone.get("id"))
        explicit_area, explicit_key = _progress_explicit_zone_area(zone)
        points = _progress_zone_points(zone)
        raw_area = _progress_polygon_area_raw(points)

        if explicit_area is None:
            explicit_complete = False
        else:
            explicit_total += explicit_area

        if raw_area is None:
            raw_complete = False
        else:
            raw_total += raw_area
            selected_polygons.append(points)

        zone_no_go_raw = _progress_polygon_union_intersection_area_raw(
            [points] if len(points) >= 3 else [], no_go_polygons
        )
        if raw_area is not None:
            selected_zone_no_go_overlaps.append(zone_no_go_raw)
        zone_no_go_m2 = (
            zone_no_go_raw * polygon_scale
            if polygon_scale is not None
            else None
        )
        zone_gross_m2 = (
            raw_area * polygon_scale
            if raw_area is not None and polygon_scale is not None
            else explicit_area
        )
        zone_net_m2 = (
            max(0.0, zone_gross_m2 - (zone_no_go_m2 or 0.0))
            if zone_gross_m2 is not None
            else None
        )

        zones_debug.append(
            {
                "id": zone_id,
                "name": zone.get("name"),
                "explicit_area": explicit_area,
                "explicit_area_key": explicit_key,
                "point_count": len(points),
                "polygon_area_raw": round(raw_area, 3) if raw_area is not None else None,
                "no_go_overlap_raw": round(zone_no_go_raw, 3),
                "no_go_overlap_m2": round(zone_no_go_m2, 3)
                if zone_no_go_m2 is not None
                else None,
                "gross_calibrated_area_m2": round(zone_gross_m2, 3)
                if zone_gross_m2 is not None
                else None,
                "net_mowable_area_m2": round(zone_net_m2, 3)
                if zone_net_m2 is not None
                else None,
            }
        )

    selected_raw = raw_total if raw_complete and raw_total > 0 else None
    explicit_value = explicit_total if explicit_complete and explicit_total > 0 else None

    # For zone mowing, subtract the UNION of all No-Go overlap with the UNION
    # of all selected zones. This avoids double subtraction when No-Go areas
    # overlap each other or when multiple mowing zones are selected.
    if active_ids:
        overlap_zone_polygons = selected_polygons
    else:
        overlap_zone_polygons = [
            points
            for zone in all_zones
            if len(points := _progress_zone_points(zone)) >= 3
        ]

    if (
        active_ids
        and len(selected_polygons) == 1
        and len(selected_zone_no_go_overlaps) == 1
    ):
        no_go_overlap_raw = selected_zone_no_go_overlaps[0]
    else:
        no_go_overlap_raw = _progress_polygon_union_intersection_area_raw(
            overlap_zone_polygons, no_go_polygons
        )
    no_go_overlap_m2 = (
        no_go_overlap_raw * polygon_scale
        if polygon_scale is not None
        else None
    )

    gross_calibrated_area = None
    calibrated_area = None
    area_source = None

    if active_ids:
        if explicit_value is not None:
            gross_calibrated_area = explicit_value
            calibrated_area = max(
                0.0,
                gross_calibrated_area - (no_go_overlap_m2 or 0.0),
            )
            area_source = (
                "active_zone_explicit_area_no_go_adjusted"
                if no_go_overlap_m2 is not None and no_go_overlap_m2 > 0
                else "active_zone_explicit_area"
            )
        elif selected_raw is not None and polygon_scale is not None:
            gross_calibrated_area = selected_raw * polygon_scale
            calibrated_area = max(
                0.0,
                gross_calibrated_area - (no_go_overlap_m2 or 0.0),
            )
            area_source = (
                "active_zone_polygon_calibrated_to_map_area_no_go_adjusted"
                if no_go_overlap_m2 is not None and no_go_overlap_m2 > 0
                else "active_zone_polygon_calibrated_to_map_area"
            )
        else:
            area_source = "active_zone_area_unavailable"
    else:
        gross_calibrated_area = map_area if map_area is not None and map_area > 0 else None
        if gross_calibrated_area is not None:
            calibrated_area = max(
                0.0,
                gross_calibrated_area - (no_go_overlap_m2 or 0.0),
            )
            area_source = (
                "full_map_area_no_go_adjusted"
                if no_go_overlap_m2 is not None and no_go_overlap_m2 > 0
                else "full_map_area"
            )
        else:
            area_source = "full_map_area_unavailable"

    no_go_polygon_raw_sum = 0.0
    for points in no_go_polygons:
        raw_area = _progress_polygon_area_raw(points)
        if raw_area is not None:
            no_go_polygon_raw_sum += raw_area

    return {
        "active_zone_ids": active_ids,
        "matched_zone_count": len(selected),
        "explicit_area_total": round(explicit_value, 3) if explicit_value is not None else None,
        "polygon_area_raw_total": round(selected_raw, 3) if selected_raw is not None else None,
        "all_zone_polygon_raw_total": round(all_raw, 3) if all_raw is not None else None,
        "all_zone_polygon_valid_count": all_raw_valid_count,
        "all_zone_count": all_zone_count,
        "polygon_scale_m2_per_raw_unit2": polygon_scale,
        "no_go_count": len(no_go_zones),
        "no_go_valid_polygon_count": len(no_go_polygons),
        "no_go_polygon_raw_sum": round(no_go_polygon_raw_sum, 3),
        "no_go_active_overlap_raw_total": round(no_go_overlap_raw, 3),
        "no_go_active_overlap_m2": round(no_go_overlap_m2, 3)
        if no_go_overlap_m2 is not None
        else None,
        "gross_calibrated_area_total_m2": round(gross_calibrated_area, 3)
        if gross_calibrated_area is not None
        else None,
        "calibrated_area_total_m2": round(calibrated_area, 3)
        if calibrated_area is not None
        else None,
        "area_source": area_source,
        "zones_debug": zones_debug,
    }


def _progress_learning_key(data: dict[str, Any]) -> str:
    active_ids = sorted(set(active_manual_zone_ids(data)))
    if active_ids:
        return "manual:" + ",".join(str(zone_id) for zone_id in active_ids)
    learning = data.get("_mowing_area_learning")
    if isinstance(learning, dict):
        current_key = learning.get("current_key")
        if isinstance(current_key, str) and current_key:
            return current_key
    return "full"


def _progress_learning_debug(data: dict[str, Any]) -> dict[str, Any]:
    learning = data.get("_mowing_area_learning")
    key = _progress_learning_key(data)
    profile = None
    sample_limit = 3
    if isinstance(learning, dict):
        raw_limit = learning.get("sample_limit")
        if isinstance(raw_limit, int) and raw_limit > 0:
            sample_limit = raw_limit
        profiles = learning.get("profiles")
        if isinstance(profiles, dict):
            candidate = profiles.get(key)
            if isinstance(candidate, dict):
                profile = candidate

    reference = _progress_float(profile.get("reference_m2")) if profile else None
    raw_samples = profile.get("samples_m2") if profile else None
    samples = (
        [
            number
            for value in raw_samples
            if (number := _progress_float(value)) is not None and number > 0
        ]
        if isinstance(raw_samples, list)
        else []
    )
    sample_count = len(samples)
    return {
        "learned_zone_mowing_key": key,
        "learned_zone_mowing_area_m2": round(reference, 3)
        if reference is not None and reference > 0
        else None,
        "learned_zone_mowing_samples_m2": [round(value, 3) for value in samples],
        "learned_zone_mowing_sample_count": sample_count,
        "learned_zone_mowing_sample_limit": sample_limit,
        "learned_zone_mowing_confidence": (
            "stable"
            if sample_count >= sample_limit
            else "building"
            if sample_count > 1
            else "provisional"
            if sample_count == 1
            else "unlearned"
        ),
        "learned_zone_mowing_profiles": learning.get("profiles", {})
        if isinstance(learning, dict) and isinstance(learning.get("profiles"), dict)
        else {},
    }


def _progress_target_area(data: dict[str, Any]) -> tuple[float | None, str]:
    learning = _progress_learning_debug(data)
    learned_target = _progress_float(learning.get("learned_zone_mowing_area_m2"))
    if learned_target is not None and learned_target > 0:
        return learned_target, "learned_zone_mowing_area"

    debug = _progress_active_zone_debug(data)
    target = _progress_float(debug.get("calibrated_area_total_m2"))
    source = str(debug.get("area_source") or "unavailable")
    if target is None or target <= 0:
        return None, source
    return target, source


def _mowing_progress(data: dict[str, Any]) -> float | None:
    mowing_area = _progress_float(_safe_get(data, "mowing_area_new", "value"))
    if mowing_area is None or mowing_area < 0:
        return None

    target, _source = _progress_target_area(data)
    if target is None or target <= 0:
        return None

    progress = (mowing_area / target) * 100.0
    return round(max(0.0, min(progress, 100.0)), 1)


def _active_zone_area(data: dict[str, Any]) -> float | None:
    debug = _progress_active_zone_debug(data)
    return _progress_float(debug.get("calibrated_area_total_m2"))


def _as_datetime(value: Any) -> datetime | None:
    """Parse Unix-epoch integers and 'YYYYMMDDHHMMSS' strings to UTC datetimes."""
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and len(value) == 14 and value.isdigit():
        try:
            anthbot_timezone = timezone(timedelta(hours=8))
            return (
                datetime.strptime(value, "%Y%m%d%H%M%S")
                .replace(tzinfo=anthbot_timezone)
                .astimezone(timezone.utc)
            )
        except ValueError:
            return None
    return None


def _is_custom_mowing_direction_enabled(data: dict[str, Any]) -> bool:
    """Map raw enable_adaptive_head value to custom-direction state."""
    param_set = data.get("param_set")
    if not isinstance(param_set, dict):
        return False
    value = param_set.get("enable_adaptive_head")
    adaptive_enabled = False
    if isinstance(value, bool):
        adaptive_enabled = value
    elif isinstance(value, int):
        adaptive_enabled = value == 1
    elif isinstance(value, str):
        adaptive_enabled = value == "1"
    return not adaptive_enabled


_ROBOT_STATUS_BY_CODE: tuple[str, ...] = (
    "idle",
    "pause",
    "charge",
    "sleep",
    "ota",
    "position",
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "mapping",
    "backtodock",
    "resume_point",
    "shutdown",
    "remotectrl",
    "factory",
    "sleep",
    "camera_cleaning",
    "gototarget",
    "bordermowing",
    "regionmowing",
    "nestmowing",
)

MOWER_STATUS_OPTIONS: list[str] = [
    "standby",
    "paused",
    "charging",
    "mowing",
    "returning_to_dock",
    "mapping",
    "positioning",
    "resuming",
    "sleeping",
    "ota_updating",
    "remote_control",
    "factory_mode",
    "camera_cleaning",
    "going_to_target",
    "shutdown",
    "unknown",
]


def _raw_robot_status(data: dict[str, Any]) -> str | None:
    """Return raw robot status from shadow payload."""
    robot_sta = data.get("robot_sta")
    if not isinstance(robot_sta, dict):
        return None
    value = robot_sta.get("value")
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, int):
        if 0 <= value < len(_ROBOT_STATUS_BY_CODE):
            return _ROBOT_STATUS_BY_CODE[value]
        return str(value)
    return None


def _general_mower_status(data: dict[str, Any]) -> str:
    """Map raw robot status to a human-readable general status."""
    raw = _raw_robot_status(data)
    if raw is None:
        return "unknown"

    if raw in {
        "globalmowing",
        "zonemowing",
        "pointmowing",
        "bordermowing",
        "regionmowing",
        "nestmowing",
    }:
        return "mowing"
    if raw in {"charge", "charging", "charge_start"}:
        return "charging"
    if raw == "backtodock":
        return "returning_to_dock"
    if raw == "idle":
        return "standby"
    if raw == "pause":
        return "paused"
    if raw == "mapping":
        return "mapping"
    if raw == "position":
        return "positioning"
    if raw == "resume_point":
        return "resuming"
    if raw == "sleep":
        return "sleeping"
    if raw == "ota":
        return "ota_updating"
    if raw == "remotectrl":
        return "remote_control"
    if raw == "factory":
        return "factory_mode"
    if raw == "camera_cleaning":
        return "camera_cleaning"
    if raw == "gototarget":
        return "going_to_target"
    if raw == "shutdown":
        return "shutdown"
    return "unknown"


@dataclass(frozen=True, kw_only=True)
class AnthbotSensorDescription(SensorEntityDescription):
    """Describes an Anthbot sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]


def _error_description(data: dict[str, Any]) -> str | None:
    code = _as_int(data.get("err_code"))
    if code is None:
        return None
    return ERROR_CODE_DESCRIPTIONS.get(code, f"Unknown error ({code})")


def _rtk_state_label(data: dict[str, Any]) -> str | None:
    code = _as_int(data.get("rtk_state"))
    if code is None:
        return None
    return RTK_STATE_OPTIONS.get(code, "unknown")


def _rtk_base_state_label(data: dict[str, Any]) -> str | None:
    code = _as_int(_safe_get(data, "ctl_rtk_base", "rtk_base_state"))
    if code is None:
        return None
    return RTK_BASE_STATE_OPTIONS.get(code, "unknown")


SENSORS: tuple[AnthbotSensorDescription, ...] = (
    # --- Primary mower status --------------------------------------------
    AnthbotSensorDescription(
        key="mower_status",
        translation_key="mower_status",
        name="Mower status",
        device_class=SensorDeviceClass.ENUM,
        options=MOWER_STATUS_OPTIONS,
        value_fn=_general_mower_status,
    ),
    AnthbotSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery_level,
    ),
    AnthbotSensorDescription(
        key="voice_volume",
        translation_key="voice_volume",
        name="Voice volume",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("volume"),
    ),
    AnthbotSensorDescription(
        key="cutting_height",
        translation_key="cutting_height",
        name="Cutting height",
        native_unit_of_measurement="mm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            _safe_get(data, "param_set", "cutter_height")
            or _safe_get(data, "mow_remote", "cutter_height")
        ),
    ),
    AnthbotSensorDescription(
        key="mowing_time",
        translation_key="mowing_time",
        name="Mowing time (session)",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "mowing_time_new", "value"),
    ),
    AnthbotSensorDescription(
        key="mowing_area",
        translation_key="mowing_area",
        name="Mowing area (session)",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "mowing_area_new", "value"),
    ),


    # --- MOWING PROGRESS v2.4.3-beta.2 ---
    AnthbotSensorDescription(
        key="mowing_progress",
        name="Mowing progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_mowing_progress,
    ),
    AnthbotSensorDescription(
        key="active_zone_area",
        name="Active zone area",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_active_zone_area,
    ),
    AnthbotSensorDescription(
        key="custom_mowing_direction",
        translation_key="custom_mowing_direction",
        name="Custom mowing direction",
        native_unit_of_measurement="deg",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "param_set", "mow_head"),
    ),
    AnthbotSensorDescription(
        key="custom_mowing_direction_enabled",
        translation_key="custom_mowing_direction_enabled",
        name="Custom mowing direction enabled",
        device_class=SensorDeviceClass.ENUM,
        options=["enabled", "disabled"],
        value_fn=lambda data: (
            "enabled" if _is_custom_mowing_direction_enabled(data) else "disabled"
        ),
    ),
    AnthbotSensorDescription(
        key="zones",
        translation_key="zones",
        name="Zones",
        value_fn=lambda data: len(manual_zones(data)),
    ),
    AnthbotSensorDescription(
        key="auto_zones",
        translation_key="auto_zones",
        name="Auto zones",
        value_fn=lambda data: len(auto_zones(data)),
    ),
    # --- Map / area ------------------------------------------------------
    AnthbotSensorDescription(
        key="total_map_area",
        translation_key="total_map_area",
        name="Total mapped area",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("map_area"),
    ),
    AnthbotSensorDescription(
        key="map_status",
        translation_key="map_status",
        name="Map status",
        value_fn=lambda data: _safe_get(data, "map_sta", "value"),
    ),
    # --- Errors / events -------------------------------------------------
    AnthbotSensorDescription(
        key="error_code",
        translation_key="error_code",
        name="Error code",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _as_int(data.get("err_code")),
    ),
    AnthbotSensorDescription(
        key="error_description",
        translation_key="error_description",
        name="Error description",
        value_fn=_error_description,
    ),
    AnthbotSensorDescription(
        key="event_code",
        translation_key="event_code",
        name="Last event code",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _as_int(data.get("event_code")),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_code",
        name="Cloud task event code",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: task_event_code(data.get("_task_events")),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_text",
        name="Cloud task event text",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: task_event_value(
            data.get("_task_events"), "event_message"
        ),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_type",
        name="Cloud task event type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: task_event_value(data.get("_task_events"), "code_type"),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_time",
        name="Cloud task event time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: task_event_datetime(data.get("_task_events")),
    ),
    # --- Positioning / RTK ----------------------------------------------
    AnthbotSensorDescription(
        key="rtk_state",
        translation_key="rtk_state",
        name="RTK fix state",
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(list(RTK_STATE_OPTIONS.values()) + ["unknown"])),
        value_fn=_rtk_state_label,
    ),
    AnthbotSensorDescription(
        key="rtk_base_state",
        translation_key="rtk_base_state",
        name="RTK base station state",
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(list(RTK_BASE_STATE_OPTIONS.values()) + ["unknown"])),
        value_fn=_rtk_base_state_label,
    ),
    AnthbotSensorDescription(
        key="gps_latitude",
        translation_key="gps_latitude",
        name="GPS latitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "anti_loss_pose", "posegps", "lat"),
    ),
    AnthbotSensorDescription(
        key="gps_longitude",
        translation_key="gps_longitude",
        name="GPS longitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "anti_loss_pose", "posegps", "lon"),
    ),
    # --- Maintenance percentages ----------------------------------------
    AnthbotSensorDescription(
        key="cutting_component_life",
        translation_key="cutting_component_life",
        name="Cutting components life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "robot_maintenance", "ccp_pecent"),
    ),
    AnthbotSensorDescription(
        key="cutting_line_life",
        translation_key="cutting_line_life",
        name="Cutting line life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "robot_maintenance", "cl_pecent"),
    ),
    AnthbotSensorDescription(
        key="recharge_contact_life",
        translation_key="recharge_contact_life",
        name="Recharge contact life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "robot_maintenance", "rc_pecent"),
    ),
    # --- Firmware / versions --------------------------------------------
    AnthbotSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        name="Firmware version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "system_version"),
    ),
    AnthbotSensorDescription(
        key="main_board_version",
        translation_key="main_board_version",
        name="Main board version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "main_board"),
    ),
    AnthbotSensorDescription(
        key="extension_board_version",
        translation_key="extension_board_version",
        name="Extension board version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "exten_board"),
    ),
    AnthbotSensorDescription(
        key="rtk_base_firmware",
        translation_key="rtk_base_firmware",
        name="RTK base firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "rtk_base"),
    ),
    AnthbotSensorDescription(
        key="protocol_version",
        translation_key="protocol_version",
        name="Protocol version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("protocol_version"),
    ),
    AnthbotSensorDescription(
        key="minimum_app_version",
        translation_key="minimum_app_version",
        name="Minimum app version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("min_app_version"),
    ),
    # --- OTA -------------------------------------------------------------
    AnthbotSensorDescription(
        key="ota_progress",
        translation_key="ota_progress",
        name="OTA progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "ota_status", "ota_progress"),
    ),
    AnthbotSensorDescription(
        key="ota_state",
        translation_key="ota_state",
        name="OTA state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "ota_status", "ota_state"),
    ),
    AnthbotSensorDescription(
        key="ota_time_estimate",
        translation_key="ota_time_estimate",
        name="OTA time estimate",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "ota_status", "ota_time_estimate"),
    ),
    # --- Network diagnostics --------------------------------------------
    AnthbotSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        name="WiFi SSID",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("sta_ssid"),
    ),
    AnthbotSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        name="IP address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("sta_ip_addr"),
    ),
    AnthbotSensorDescription(
        key="sim_ccid",
        translation_key="sim_ccid",
        name="SIM CCID",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("4g_ccid"),
    ),
    # --- Misc diagnostics -----------------------------------------------
    AnthbotSensorDescription(
        key="pin_code",
        translation_key="pin_code",
        name="Device PIN",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_int(data.get("pin_code")),
    ),
    AnthbotSensorDescription(
        key="voice_language",
        translation_key="voice_language",
        name="Voice language",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _safe_get(data, "voice_status", "name")
            or _safe_get(data, "music_cfg", "music_language")
        ),
    ),
    AnthbotSensorDescription(
        key="obstacle_avoidance_level",
        translation_key="obstacle_avoidance_level",
        name="Obstacle avoidance level",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "pobctl", "level"),
    ),
    AnthbotSensorDescription(
        key="mow_count",
        translation_key="mow_count",
        name="Pass count setting",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "param_set", "mow_count"),
    ),
    AnthbotSensorDescription(
        key="anti_loss_radius",
        translation_key="anti_loss_radius",
        name="Anti-loss radius",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_int(data.get("anti_loss_radius")),
    ),
    # --- v1.0.0: Absolute pose ------------------------------------------
    # `pose` reports x/y in cm and yaw in degrees, separate from the
    # (lat,lon) GPS reading. Useful for plotting on a 2D map.
    AnthbotSensorDescription(
        key="pose_x",
        translation_key="pose_x",
        name="Position X",
        native_unit_of_measurement="cm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "pose", "x"),
    ),
    AnthbotSensorDescription(
        key="pose_y",
        translation_key="pose_y",
        name="Position Y",
        native_unit_of_measurement="cm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "pose", "y"),
    ),
    AnthbotSensorDescription(
        key="pose_yaw",
        translation_key="pose_yaw",
        name="Heading",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "pose", "yaw"),
    ),
    # --- v1.0.0: Active mowing zone -------------------------------------
    AnthbotSensorDescription(
        key="active_zone_id",
        translation_key="active_zone_id",
        name="Active zone",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _safe_get(data, "active_area", "id")[0]
            if isinstance(_safe_get(data, "active_area", "id"), list)
            and _safe_get(data, "active_area", "id")
            else None
        ),
    ),
    # --- v1.0.0: Forbid (no-go) zones count ------------------------------
    AnthbotSensorDescription(
        key="forbid_zones_count",
        translation_key="forbid_zones_count",
        name="No-go zones",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            len(_safe_get(data, "_area_definition", "forbid_areas") or [])
        ),
    ),
    # --- Timestamps ------------------------------------------------------
    AnthbotSensorDescription(
        key="shadow_updated",
        translation_key="shadow_updated",
        name="Shadow last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("timestamp")),
    ),
    AnthbotSensorDescription(
        key="system_boot_time",
        translation_key="system_boot_time",
        name="System boot time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("system_boot_time")),
    ),
    AnthbotSensorDescription(
        key="map_last_updated",
        translation_key="map_last_updated",
        name="Map last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("map_time")),
    ),
    AnthbotSensorDescription(
        key="path_last_updated",
        translation_key="path_last_updated",
        name="Path last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("path_time")),
    ),
    AnthbotSensorDescription(
        key="area_last_updated",
        translation_key="area_last_updated",
        name="Area last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("area_time")),
    ),
    AnthbotSensorDescription(
        key="next_appointment",
        translation_key="next_appointment",
        name="Next appointment",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("appointment_time")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot sensors from config entry."""

    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]

    entities = [
        AnthbotSensorEntity(coordinator, description)
        for coordinator in coordinators
        for description in SENSORS
    ]

    entities.extend(
        AnthbotMapSensorEntity(coordinator)
        for coordinator in coordinators
    )

    async_add_entities(entities)


class AnthbotSensorEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SensorEntity
):
    """Anthbot sensor entity."""

    entity_description: AnthbotSensorDescription
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset(
        {"latest_task_event", "task_events", "task_events_error"}
    )

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def native_value(self) -> Any:
        """Return current sensor value."""
        return self.entity_description.value_fn(self.coordinator.reported_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        state = self.coordinator.reported_state
        cutting_height = (
            state.get("param_set", {}).get("cutter_height")
            if isinstance(state.get("param_set"), dict)
            else (
                state.get("mow_remote", {}).get("cutter_height")
                if isinstance(state.get("mow_remote"), dict)
                else None
            )
        )
        mowing_time = (
            state.get("mowing_time_new", {}).get("value")
            if isinstance(state.get("mowing_time_new"), dict)
            else None
        )
        mowing_area = (
            state.get("mowing_area_new", {}).get("value")
            if isinstance(state.get("mowing_area_new"), dict)
            else None
        )
        custom_mowing_direction = (
            state.get("param_set", {}).get("mow_head")
            if isinstance(state.get("param_set"), dict)
            else None
        )
        custom_mowing_direction_enabled = (
            _is_custom_mowing_direction_enabled(state)
            if isinstance(state.get("param_set"), dict)
            else False
        )
        voice_volume = state.get("volume")
        voice_status = (
            state.get("voice_status")
            if isinstance(state.get("voice_status"), dict)
            else None
        )
        rain_continue_time = state.get("rain_continue_time")
        mower_status = _general_mower_status(state)
        robot_status_raw = _raw_robot_status(state)
        attributes = {
            "serial_number": self.coordinator.client.serial_number,
            "mower_status": mower_status,
            "robot_status_raw": robot_status_raw,
            "cutting_height": cutting_height,
            "mowing_time": mowing_time,
            "mowing_area": mowing_area,
            "custom_mowing_direction": custom_mowing_direction,
            "custom_mowing_direction_enabled": custom_mowing_direction_enabled,
            "voice_volume": voice_volume,
            "voice_status": voice_status,
            "rain_continue_time": rain_continue_time,
        }
        if self.entity_description.key == "zones":
            manual_zone_list = manual_zones(state)
            attributes["zone_ids"] = [
                zone_id
                for zone in manual_zone_list
                if isinstance((zone_id := zone.get("id")), int)
            ]
            attributes["zone_names"] = [
                zone_name
                for zone in manual_zone_list
                if isinstance((zone_name := zone.get("name")), str) and zone_name
            ]
            attributes["active_zone_ids"] = active_manual_zone_ids(state)
        if self.entity_description.key == "auto_zones":
            auto_zone_list = auto_zones(state)
            attributes["auto_zone_ids"] = [
                zone_id
                for zone in auto_zone_list
                if isinstance((zone_id := zone.get("id")), int)
            ]
            attributes["auto_zone_names"] = [
                zone_name
                for zone in auto_zone_list
                if isinstance((zone_name := zone.get("name")), str) and zone_name
            ]


        # --- MOWING PROGRESS v2.4.3-beta.2 ---
        if self.entity_description.key in {
            "mowing_progress",
            "active_zone_area",
        }:
            zone_debug = _progress_active_zone_debug(state)
            progress_target, progress_source = _progress_target_area(state)
            learning_debug = _progress_learning_debug(state)
            attributes["progress_source"] = progress_source
            attributes["progress_target_area_m2"] = (
                round(progress_target, 3) if progress_target is not None else None
            )
            attributes["progress_mowing_area_m2"] = _progress_float(
                _safe_get(state, "mowing_area_new", "value")
            )
            attributes["progress_map_area_m2"] = _progress_float(
                state.get("map_area")
            )
            attributes.update(zone_debug)
            attributes.update(learning_debug)
        if self.entity_description.key == "cloud_task_event_code":
            payload = state.get("_task_events")
            attributes["latest_task_event"] = latest_task_event(payload)
            attributes["task_events"] = task_event_items(payload)
            attributes["task_events_error"] = state.get("_task_events_error")
        return attributes
        
class AnthbotMapSensorEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SensorEntity
):
    """Anthbot map entity."""

    _unrecorded_attributes = frozenset(
        {
            "pose",
            "serial_number",
            "model",
            "mower_status",
            "robot_status_raw",
            "cur_pose",
            "map_scan_pose",
            "path",
            "cloud_path",
            "mowed_path",
            "path_id",
            "path_start",
            "path_task_type",
            "path_point_count",
            "path_coordinate_scale",
            "path_first_point",
            "map_time",
            "path_time",
            "area_time",
            "ridable_area_time",
            "history_path_info",
            "history_path_source",
            "history_path_live_refresh",
            "history_path_refresh_interval",
            "history_path_download_source",
            "area_definition",
            "ridable_areas",
            "ridable_area_error",
            "map_definition_status",
            "path_definition_status",
            "map_raster",
            "map_definition_preview",
            "map_archive_selection",
            "path_definition_preview",
            "path_point_types",
            "map_binary_paths",
            "path_binary_paths",
            "map_definition_error",
            "path_definition_error",
            "cloud_connected",
            "cloud_last_success",
            "cloud_error",
            "robot_online",
            "live_shadow_connected",
            "live_shadow_error",
            "last_mowing_task",
            "custom_button_actions_configured",
            "custom_button_actions_enabled",
            "custom_button_actions",
            "mowing_records",
            "mowing_records_error",
            "task_events",
            "task_events_error",
            "error_history",
            "maintenance",
        }
    )
    _attr_has_entity_name = True
    _attr_name = "Map"
    _attr_icon = "mdi:map"

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_map"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def native_value(self) -> str:
        return "ready"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.reported_state
        map_definition = state.get("_map_definition")
        path_definition = state.get("_path_definition")
        path_points = _definition_path_points(path_definition) or state.get("path")

        return {
            "serial_number": self.coordinator.client.serial_number,
            "model": self.coordinator.device.model,
            "pose": state.get("pose"),
            "mower_status": _general_mower_status(state),
            "robot_status_raw": _raw_robot_status(state),
            "cur_pose": state.get("curPose") or state.get("cur_pose"),
            "map_scan_pose": state.get("mapScanPose") or state.get("map_scan_pose"),
            "path": path_points,
            "cloud_path": path_points,
            "mowed_path": path_points,
            "path_id": path_definition.get("path_id") if isinstance(path_definition, dict) else None,
            "path_start": path_definition.get("start") if isinstance(path_definition, dict) else None,
            "path_task_type": path_definition.get("task_type") if isinstance(path_definition, dict) else None,
            "path_point_count": path_definition.get("point_count") if isinstance(path_definition, dict) else None,
            "path_coordinate_scale": path_definition.get("coordinate_scale") if isinstance(path_definition, dict) else None,
            "path_first_point": _definition_path_first_point(path_definition),
            "map_time": state.get("map_time"),
            "path_time": state.get("path_time"),
            "area_time": state.get("area_time"),
            "ridable_area_time": state.get("ridable_area_time"),
            "history_path_info": state.get("_history_path_info"),
            "history_path_source": state.get("_history_path_source"),
            "history_path_live_refresh": state.get("_history_path_live_refresh"),
            "history_path_refresh_interval": state.get("_history_path_refresh_interval"),
            "history_path_download_source": path_definition.get("_download_source") if isinstance(path_definition, dict) else None,
            "area_definition": state.get("_area_definition"),
            "ridable_areas": ridable_areas(state),
            "ridable_area_error": state.get("_ridable_area_definition_error"),
            "map_definition_status": _definition_status(map_definition),
            "path_definition_status": _definition_status(path_definition),
            "map_raster": _definition_map_raster(map_definition),
            "map_definition_preview": _definition_preview(map_definition),
            "map_archive_selection": state.get("_map_archive_selection"),
            "path_definition_preview": _definition_preview(path_definition),
            "path_point_types": _definition_path_type_counts(path_definition),
            "map_binary_paths": _definition_binary_paths(map_definition),
            "path_binary_paths": _definition_binary_paths(path_definition),
            "map_definition_error": state.get("_map_definition_error"),
            "path_definition_error": state.get("_path_definition_error"),
            "cloud_connected": state.get("_cloud_connected"),
            "cloud_last_success": state.get("_cloud_last_success"),
            "cloud_error": state.get("_cloud_error"),
            "robot_online": state.get("_robot_online"),
            "live_shadow_connected": state.get("_live_shadow_connected", False),
            "live_shadow_error": state.get("_live_shadow_error"),
            "last_mowing_task": self.coordinator.last_mowing_task,
            "custom_button_actions_configured": self.coordinator.custom_button_actions_configured,
            "custom_button_actions_enabled": self.coordinator.custom_button_actions_enabled,
            "custom_button_actions": self.coordinator.custom_button_actions,
            "mowing_records": state.get("_mowing_records", {"data": []}),
            "mowing_records_error": state.get("_mowing_records_error"),
            "task_events": task_event_items(state.get("_task_events")),
            "task_events_error": state.get("_task_events_error"),
            "error_history": state.get("_error_history", []),
            "maintenance": state.get("robot_maintenance") or {
                "blade": state.get("cutting_components_life"),
                "camera": state.get("camera_life"),
                "charging_contact": state.get("recharge_contact_life"),
            },
        }        


def _definition_status(value: Any) -> str:
    if isinstance(value, dict):
        return f"dict:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if value is None:
        return "not_loaded"
    return type(value).__name__


def _definition_preview(value: Any) -> Any:
    if isinstance(value, dict):
        if isinstance(value.get("_binary_probe"), dict):
            return value["_binary_probe"]
        preview: dict[str, Any] = {"keys": [str(key) for key in list(value.keys())[:20]]}
        for key, child in list(value.items())[:8]:
            preview[str(key)] = _small_shape(child)
        return preview
    if isinstance(value, list):
        return {
            "length": len(value),
            "first": _small_shape(value[0]) if value else None,
        }
    return None


def _definition_map_raster(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raster = value.get("_map_raster")
    if isinstance(raster, dict):
        return raster
    return None


def _definition_path_points(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    points = value.get("_path_points")
    if not isinstance(points, list):
        return []
    return [point for point in points if isinstance(point, dict)]


def _definition_path_first_point(value: Any) -> dict[str, Any] | None:
    points = _definition_path_points(value)
    return points[0] if points else None


def _definition_path_type_counts(value: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for point in _definition_path_points(value):
        point_type = str(point.get("type", "missing"))
        counts[point_type] = counts.get(point_type, 0) + 1
    return counts


def _small_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {"type": "dict", "keys": [str(key) for key in list(value.keys())[:10]]}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first": _small_shape(value[0]) if value else None,
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return type(value).__name__


def _definition_binary_paths(value: Any) -> list[dict[str, Any]]:
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
