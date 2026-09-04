"""M-series mowing-history zone recovery from captured record start points.

Real M9 Pro captures (2026-09-04) show that completed zone-mowing records can
omit ``zone_id``/``zone_list`` even though the live property shadow exposes the
selected area as ``active_area.id``.  The same history row does retain its
start ``x``/``y`` coordinates in metres, while ``area_setting.json`` stores
zone polygons in millimetres.  Recovering the unique containing custom area
lets the existing frontend calculate an honest per-zone mowing percentage
without changing Genie behaviour or inventing a percentage from the vendor's
opaque record fields.
"""

from __future__ import annotations

import math
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator

_INSTALLED = False
_ZONE_LIST_KEYS = (
    "zone_list",
    "zoneList",
    "zones",
    "region_list",
    "regionList",
    "area_list",
    "areaList",
    "task_zones",
    "taskZones",
    "zone_info",
    "zoneInfo",
)
_ZONE_ID_KEYS = (
    "zone_id",
    "zoneId",
    "zone_ids",
    "zoneIds",
    "mow_zone",
    "mowZone",
    "region_id",
    "regionId",
    "region_ids",
    "regionIds",
    "area_id",
    "areaId",
)


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _is_zone_record(record: dict[str, Any]) -> bool:
    value = record.get("mow_mode", record.get("mowMode", record.get("mode")))
    if isinstance(value, (int, float)):
        return int(value) == 1
    normalized = str(value or "").strip().lower()
    return normalized == "1" or any(
        token in normalized for token in ("zone", "zona", "zóna")
    )


def _has_explicit_zone(record: dict[str, Any]) -> bool:
    for key in (*_ZONE_LIST_KEYS, *_ZONE_ID_KEYS):
        value = record.get(key)
        if value not in (None, "", [], {}):
            return True
    return False


def _zone_points(zone: dict[str, Any]) -> list[tuple[float, float]]:
    value = zone.get("vertexs", zone.get("vertices", zone.get("points", [])))
    if not isinstance(value, list):
        return []
    points: list[tuple[float, float]] = []
    for item in value:
        if isinstance(item, dict):
            x, y = item.get("x"), item.get("y")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x, y = item[0], item[1]
        else:
            continue
        try:
            px, py = float(x), float(y)
        except (TypeError, ValueError):
            continue
        if math.isfinite(px) and math.isfinite(py):
            points.append((px, py))
    return points


def _point_on_segment(
    x: float,
    y: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> bool:
    dx = bx - ax
    dy = by - ay
    cross = (x - ax) * dy - (y - ay) * dx
    tolerance = 1e-7 * max(1.0, abs(dx) + abs(dy))
    if abs(cross) > tolerance:
        return False
    dot = (x - ax) * dx + (y - ay) * dy
    return 0.0 <= dot <= dx * dx + dy * dy


def _point_in_polygon(x: float, y: float, points: list[tuple[float, float]]) -> bool:
    if len(points) < 3:
        return False
    inside = False
    previous = len(points) - 1
    for current, (cx, cy) in enumerate(points):
        px, py = points[previous]
        if _point_on_segment(x, y, px, py, cx, cy):
            return True
        if (cy > y) != (py > y):
            crossing_x = (px - cx) * (y - cy) / (py - cy) + cx
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def _infer_zone(record: dict[str, Any], area_definition: Any) -> dict[str, Any] | None:
    if not _is_zone_record(record) or _has_explicit_zone(record):
        return None
    if not isinstance(area_definition, dict):
        return None

    try:
        # Captured M9 Pro /api/v1/device/area rows expose x/y in metres.
        x = float(record.get("x", record.get("X"))) * 1000.0
        y = float(record.get("y", record.get("Y"))) * 1000.0
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None

    zones = area_definition.get("custom_areas")
    if not isinstance(zones, list):
        zones = area_definition.get("customAreas")
    if not isinstance(zones, list):
        zones = area_definition.get("zones")
    if not isinstance(zones, list):
        return None

    matches: list[dict[str, Any]] = []
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        points = _zone_points(zone)
        if _point_in_polygon(x, y, points):
            matches.append(zone)

    # Be conservative: never guess when polygons overlap or the point is outside.
    return matches[0] if len(matches) == 1 else None


def _enrich_history(state: dict[str, Any]) -> tuple[dict[str, Any], Any | None]:
    payload = state.get("_mowing_records")
    area_definition = state.get("_area_definition")
    if isinstance(payload, dict):
        records = payload.get("data")
    elif isinstance(payload, list):
        records = payload
    else:
        return state, None
    if not isinstance(records, list) or not isinstance(area_definition, dict):
        return state, None

    changed = False
    enriched_records: list[Any] = []
    for raw_record in records:
        if not isinstance(raw_record, dict):
            enriched_records.append(raw_record)
            continue
        zone = _infer_zone(raw_record, area_definition)
        if zone is None:
            enriched_records.append(raw_record)
            continue
        zone_id = zone.get("id")
        if zone_id is None:
            enriched_records.append(raw_record)
            continue
        record = dict(raw_record)
        zone_item: dict[str, Any] = {"id": zone_id}
        zone_name = zone.get("name")
        if isinstance(zone_name, str) and zone_name:
            zone_item["name"] = zone_name
        record["zone_list"] = [zone_item]
        enriched_records.append(record)
        changed = True

    if not changed:
        return state, None

    if isinstance(payload, dict):
        enriched_payload = dict(payload)
        enriched_payload["data"] = enriched_records
    else:
        enriched_payload = enriched_records
    result = dict(state)
    result["_mowing_records"] = enriched_payload
    return result, enriched_payload


def install_m_series_history_support() -> None:
    """Recover missing M-series history zone ids from record start positions."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data

    async def update_data(self: AnthbotGenieDataUpdateCoordinator) -> dict[str, Any]:
        state = await previous_update(self)
        if not _is_m_series(getattr(self.device, "model", None)):
            return state
        enriched, payload = _enrich_history(state)
        if payload is not None:
            # Keep the coordinator cache aligned with the state exposed to HA.
            self._mowing_records = payload  # noqa: SLF001 - model adapter
        return enriched

    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
