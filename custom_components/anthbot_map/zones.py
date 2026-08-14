"""Zone parsing helpers for Anthbot Genie."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from .api import AnthbotGenieApiError


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


def ridable_areas(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return editable boundary/edge definitions used by the mobile app."""
    separate = data.get("_ridable_area_definition")
    if isinstance(separate, list):
        edges = _list_of_dicts(separate)
        if edges:
            return edges
    if isinstance(separate, dict):
        for key in ("ridable_areas", "ridableAreas", "areas", "data"):
            edges = _list_of_dicts(separate.get(key))
            if edges:
                return edges
    area_definition = _area_definition(data)
    for key in ("ridable_areas", "ridableAreas"):
        edges = _list_of_dicts(area_definition.get(key))
        if edges:
            return edges
    return _list_of_dicts(data.get("ridable_areas"))


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
            "ride_distance",
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


def _coerce_zone_id(value: Any) -> int | None:
    """Return a zone id accepted by the mower."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


async def async_update_zone_settings(
    coordinator: Any,
    *,
    zone_kind: str,
    zone_id: int,
    updates: dict[str, Any],
) -> None:
    """Persist one zone using the app-compatible full area_set payload."""
    state = coordinator.reported_state
    source = manual_zones(state) if zone_kind == "manual" else auto_zones(state)
    if not source:
        raise AnthbotGenieApiError("No zone definition is available")

    zones = deepcopy(source)
    matched = False
    for zone in zones:
        if _coerce_zone_id(zone.get("id")) != zone_id:
            continue
        zone.update(updates)
        matched = True
        break
    if not matched:
        raise AnthbotGenieApiError(f"Zone {zone_id} was not found")

    if zone_kind == "manual":
        data = {"custom_areas": zones, "delete_custom_areas": []}
    elif zone_kind == "auto":
        data = {"region_areas": zones}
    else:
        raise AnthbotGenieApiError(f"Unsupported zone kind: {zone_kind}")

    await coordinator.client.async_publish_service_command(cmd="area_set", data=data)
    await asyncio.sleep(2)
    await coordinator.client.async_request_all_properties()
    await coordinator.async_request_refresh()


async def async_update_edge_settings(
    coordinator: Any,
    *,
    edge_id: int,
    cutter_height: int,
    ride_distance: int,
) -> None:
    """Persist one map edge with the app-compatible ridable_area_set payload."""
    source = ridable_areas(coordinator.reported_state)
    if not source:
        raise AnthbotGenieApiError("No editable edge definition is available")

    edges = deepcopy(source)
    matched = False
    for edge in edges:
        if _coerce_zone_id(edge.get("id")) != edge_id:
            continue
        edge["cutter_height"] = cutter_height
        edge["ride_distance"] = ride_distance
        matched = True
        break
    if not matched:
        raise AnthbotGenieApiError(f"Edge {edge_id} was not found")

    previous_time = coordinator.reported_state.get("ridable_area_time")
    if not isinstance(previous_time, str):
        previous_time = None

    await coordinator.client.async_publish_service_command(
        cmd="ridable_area_set",
        data={"ridable_areas": edges, "delete_ridable_area": []},
    )
    await coordinator.async_confirm_ridable_area_settings(
        previous_time=previous_time,
        edge_id=edge_id,
        cutter_height=cutter_height,
        ride_distance=ride_distance,
    )
