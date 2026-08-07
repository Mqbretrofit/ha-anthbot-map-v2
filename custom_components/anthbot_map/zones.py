"""Zone parsing helpers for Anthbot Genie."""

from __future__ import annotations

from typing import Any


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _area_definition(data: dict[str, Any]) -> dict[str, Any]:
    area_definition = data.get("_area_definition")
    if isinstance(area_definition, dict):
        return area_definition
    return {}


def manual_zones(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return manual/custom mowing zones."""
    area_definition = _area_definition(data)
    for key in ("custom_areas", "zones", "customAreas"):
        zones = _list_of_dicts(area_definition.get(key))
        if zones:
            return zones

    return _list_of_dicts(data.get("custom_areas"))


def auto_zones(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return auto-zone definitions."""
    area_definition = _area_definition(data)
    for key in (
        "region_areas",
        "regionAreas",
        "auto_regions",
        "autoRegions",
        "auto_zones",
        "autoZones",
        "regions",
    ):
        zones = _list_of_dicts(area_definition.get(key))
        if zones:
            return zones

    return _list_of_dicts(data.get("region_areas"))


def active_manual_zone_ids(data: dict[str, Any]) -> list[int]:
    """Return active manual zone ids from shadow state."""
    active_area = data.get("active_area")
    if not isinstance(active_area, dict):
        return []
    ids = active_area.get("id")
    if not isinstance(ids, list):
        return []
    return [item for item in ids if isinstance(item, int)]


def zone_attribute_payload(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a compact attribute payload for UI/debugging."""
    payload: list[dict[str, Any]] = []
    for zone in zones:
        item: dict[str, Any] = {}
        for key in (
            "id",
            "name",
            "mow_count",
            "mow_mode",
            "mow_order",
            "cutter_height",
            "enable_adaptive_head",
            "mow_head",
            "visual_ignore_obstacle_switch",
            "obstacle_avoid_level",
            "x",
            "y",
            "vertexs",
            "points",
        ):
            value = zone.get(key)
            if value is not None:
                item[key] = value
        payload.append(item)
    return payload
