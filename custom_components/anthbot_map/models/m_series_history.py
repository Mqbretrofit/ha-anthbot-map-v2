"""M-series mowing-history zone recovery.

Real M9 Pro captures (2026-09-04) show that completed zone-mowing records from
``/api/v1/device/v3/record/list`` can omit ``zone_id``/``zone_list``.  While a
zone task is live, the property shadow exposes the exact selected ids in
``active_area.id`` and the task instance in ``mow_task.mow_zone.path_id``.
Capture that exact pairing and correlate it to the completed record's
``start_time``.  For older records where no live capture exists, retain the
conservative x/y point-in-polygon fallback: history x/y is in metres while
``area_setting.json`` polygons are in millimetres.

Only M5/M9-family coordinators use this adapter; Genie behaviour is untouched.
The vendor's ``mowing_progress`` field is deliberately ignored because the
frontend calculates its own per-zone percentage from the selected zone area.
"""

from __future__ import annotations

import math
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..zones import active_manual_zone_ids

_INSTALLED = False
_EXACT_START_TOLERANCE_SECONDS = 60.0
_MAX_LIVE_CAPTURES = 20
_MAX_RESOLVED_RECORDS = 100
_MODE_KEYS = (
    "mode",
    "mow_mode",
    "mowMode",
    "task_type",
    "taskType",
    "type",
)
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
    value: Any = None
    for key in _MODE_KEYS:
        candidate = record.get(key)
        if candidate not in (None, ""):
            value = candidate
            break
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


def _epoch_seconds(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    if number > 10_000_000_000:
        number /= 1000.0
    return number


def _record_identity(record: dict[str, Any]) -> str | None:
    for key in ("record_name", "recordName", "id"):
        value = record.get(key)
        if value not in (None, ""):
            return f"{key}:{value}"
    start = record.get("start_time", record.get("startTime"))
    if start not in (None, ""):
        return f"start:{start}"
    return None


def _zone_task_path_id(state: dict[str, Any]) -> int | None:
    mow_task = state.get("mow_task")
    if not isinstance(mow_task, dict):
        return None
    zone_task = mow_task.get("mow_zone")
    if not isinstance(zone_task, dict):
        return None
    task_state = zone_task.get("state")
    try:
        if int(task_state) != 1:
            return None
        path_id = int(zone_task.get("path_id"))
    except (TypeError, ValueError):
        return None
    return path_id if path_id > 0 else None


def _capture_live_zone_selection(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any],
) -> None:
    """Remember exact active_area ids keyed by the live M-series zone path id."""
    zone_ids = sorted(set(active_manual_zone_ids(state)))
    path_id = _zone_task_path_id(state)
    if not zone_ids or path_id is None:
        return
    started_at = _epoch_seconds(path_id)
    if started_at is None:
        return

    captures = getattr(coordinator, "_m_series_history_zone_captures", None)
    if not isinstance(captures, dict):
        captures = {}
    key = str(path_id)
    previous = captures.get(key)
    assigned_record = (
        previous.get("record_identity") if isinstance(previous, dict) else None
    )
    captures[key] = {
        "path_id": path_id,
        "started_at": started_at,
        "zone_ids": zone_ids,
        "record_identity": assigned_record,
    }
    while len(captures) > _MAX_LIVE_CAPTURES:
        captures.pop(next(iter(captures)))
    setattr(coordinator, "_m_series_history_zone_captures", captures)


def _exact_zone_ids_for_record(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    record: dict[str, Any],
) -> list[int]:
    """Return exact live-captured zone ids for this completed history row."""
    if not _is_zone_record(record) or _has_explicit_zone(record):
        return []
    identity = _record_identity(record)
    if identity is None:
        return []

    resolved = getattr(coordinator, "_m_series_history_zone_records", None)
    if not isinstance(resolved, dict):
        resolved = {}
    cached = resolved.get(identity)
    if isinstance(cached, list):
        return [value for value in cached if isinstance(value, int)]

    record_start = _epoch_seconds(record.get("start_time", record.get("startTime")))
    if record_start is None:
        return []
    captures = getattr(coordinator, "_m_series_history_zone_captures", None)
    if not isinstance(captures, dict):
        return []

    best_key: str | None = None
    best_delta: float | None = None
    best_ids: list[int] = []
    for key, capture in captures.items():
        if not isinstance(capture, dict):
            continue
        assigned = capture.get("record_identity")
        if assigned not in (None, identity):
            continue
        started_at = _epoch_seconds(capture.get("started_at"))
        raw_ids = capture.get("zone_ids")
        if started_at is None or not isinstance(raw_ids, list):
            continue
        ids = [value for value in raw_ids if isinstance(value, int)]
        if not ids:
            continue
        delta = abs(record_start - started_at)
        if delta > _EXACT_START_TOLERANCE_SECONDS:
            continue
        if best_delta is None or delta < best_delta:
            best_key = str(key)
            best_delta = delta
            best_ids = ids

    if best_key is None:
        return []

    capture = captures.get(best_key)
    if isinstance(capture, dict):
        capture["record_identity"] = identity
    resolved[identity] = list(best_ids)
    while len(resolved) > _MAX_RESOLVED_RECORDS:
        resolved.pop(next(iter(resolved)))
    setattr(coordinator, "_m_series_history_zone_records", resolved)
    return best_ids


def _custom_zones(area_definition: Any) -> list[dict[str, Any]]:
    if not isinstance(area_definition, dict):
        return []
    for key in ("custom_areas", "customAreas", "zones"):
        value = area_definition.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _zone_items_for_ids(
    zone_ids: list[int],
    area_definition: Any,
) -> list[dict[str, Any]]:
    zones = _custom_zones(area_definition)
    by_id: dict[str, dict[str, Any]] = {}
    for zone in zones:
        zone_id = zone.get("id")
        if zone_id is not None:
            by_id[str(zone_id)] = zone

    items: list[dict[str, Any]] = []
    for zone_id in zone_ids:
        item: dict[str, Any] = {"id": zone_id}
        zone = by_id.get(str(zone_id))
        if isinstance(zone, dict):
            name = zone.get("name")
            if isinstance(name, str) and name:
                item["name"] = name
        items.append(item)
    return items


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
        # Captured M9 Pro v3 history rows expose x/y in metres.
        x = float(record.get("x", record.get("X"))) * 1000.0
        y = float(record.get("y", record.get("Y"))) * 1000.0
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None

    matches: list[dict[str, Any]] = []
    for zone in _custom_zones(area_definition):
        points = _zone_points(zone)
        if _point_in_polygon(x, y, points):
            matches.append(zone)

    # Be conservative: never guess when polygons overlap or the point is outside.
    return matches[0] if len(matches) == 1 else None


def _enrich_history(
    state: dict[str, Any],
    coordinator: AnthbotGenieDataUpdateCoordinator | None = None,
) -> tuple[dict[str, Any], Any | None]:
    payload = state.get("_mowing_records")
    area_definition = state.get("_area_definition")
    if isinstance(payload, dict):
        records = payload.get("data")
    elif isinstance(payload, list):
        records = payload
    else:
        return state, None
    if not isinstance(records, list):
        return state, None

    changed = False
    enriched_records: list[Any] = []
    for raw_record in records:
        if not isinstance(raw_record, dict):
            enriched_records.append(raw_record)
            continue
        if not _is_zone_record(raw_record) or _has_explicit_zone(raw_record):
            enriched_records.append(raw_record)
            continue

        zone_items: list[dict[str, Any]] = []
        if coordinator is not None:
            exact_ids = _exact_zone_ids_for_record(coordinator, raw_record)
            if exact_ids:
                zone_items = _zone_items_for_ids(exact_ids, area_definition)

        if not zone_items:
            zone = _infer_zone(raw_record, area_definition)
            if zone is not None and zone.get("id") is not None:
                zone_items = _zone_items_for_ids([zone["id"]], area_definition)

        if not zone_items:
            enriched_records.append(raw_record)
            continue
        record = dict(raw_record)
        record["zone_list"] = zone_items
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
    """Recover missing M-series history zone ids without touching Genie."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data
    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow

    async def live_shadow(
        self: AnthbotGenieDataUpdateCoordinator,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        await previous_live(self, shadow_name, reported)
        if not _is_m_series(getattr(self.device, "model", None)):
            return
        state = self.reported_state
        if isinstance(state, dict):
            _capture_live_zone_selection(self, state)

    async def update_data(self: AnthbotGenieDataUpdateCoordinator) -> dict[str, Any]:
        state = await previous_update(self)
        if not isinstance(state, dict):
            return state
        if not _is_m_series(getattr(self.device, "model", None)):
            return state
        _capture_live_zone_selection(self, state)
        enriched, payload = _enrich_history(state, self)
        if payload is not None:
            # Keep both caches aligned. Status reuses _m_series_mowing_records
            # for five minutes between v3 downloads, so leaving that cache raw
            # would overwrite enrichment on the very next coordinator update.
            self._mowing_records = payload  # noqa: SLF001 - model adapter
            setattr(self, "_m_series_mowing_records", payload)
        return enriched

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
