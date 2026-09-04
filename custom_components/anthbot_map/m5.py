"""ANTHBOT M5 type module.

M5-specific path and map policy lives here. Shared AWS/shadow transport
remains in m_series_common.py.
"""

from typing import Any

from .base import is_m5_model
from . import m_series_common as _common

TYPE_KEY = "m5"
_PATH_MAX_POINTS = 50000
_MAP_CANDIDATES = ("multi_maps.tar.gz", "map_manager.tar.gz")


def matches(model: object) -> bool:
    return is_m5_model(model)


def _path_points_with_metadata(decoded: dict[str, Any]) -> list[dict[str, Any]]:
    raw_points = decoded.get("_path_points")
    if not isinstance(raw_points, list):
        return []
    points: list[dict[str, Any]] = []
    for raw in raw_points:
        if not isinstance(raw, dict):
            continue
        try:
            x = float(raw.get("x"))
            y = float(raw.get("y"))
        except (TypeError, ValueError):
            continue
        point = dict(raw)
        point["x"] = x
        point["y"] = y
        points.append(point)
    return points


def _bootstrap_existing_path(coordinator: Any) -> list[dict[str, Any]]:
    accumulator = getattr(coordinator, "_m_series_path_accumulator", None)
    if isinstance(accumulator, list) and accumulator:
        return list(accumulator)
    state = getattr(coordinator, "reported_state", {})
    if not isinstance(state, dict):
        return []
    for key in ("_path_definition", "path_definition"):
        definition = state.get(key)
        if isinstance(definition, dict):
            points = _path_points_with_metadata(definition)
            if points:
                return points
    for key in ("path", "mowed_path", "cloud_path"):
        value = state.get(key)
        if isinstance(value, list) and value:
            points: list[dict[str, Any]] = []
            for raw in value:
                if not isinstance(raw, dict):
                    continue
                try:
                    x = float(raw.get("x"))
                    y = float(raw.get("y"))
                except (TypeError, ValueError):
                    continue
                point = dict(raw)
                point["x"] = x
                point["y"] = y
                points.append(point)
            if points:
                return points
    return []


def _accumulate_path(
    coordinator: Any,
    decoded: dict[str, Any],
    packet_points: list[dict[str, float]],
) -> list[dict[str, Any]]:
    del packet_points
    packet = _path_points_with_metadata(decoded)
    path_id = decoded.get("path_id")
    previous_path_id = getattr(coordinator, "_m_series_path_id", None)
    try:
        start = int(decoded.get("start", 0) or 0)
    except (TypeError, ValueError):
        start = 0
    start = max(0, start)
    accumulator = _bootstrap_existing_path(coordinator)
    if previous_path_id is not None and previous_path_id != path_id and start == 0:
        accumulator = []
    if packet:
        if start == 0:
            accumulator = list(packet)
        elif accumulator:
            if start <= len(accumulator):
                end = start + len(packet)
                if end <= len(accumulator):
                    accumulator[start:end] = packet
                else:
                    accumulator[start:] = packet
            else:
                accumulator.extend(packet)
        else:
            accumulator = list(packet)
    setattr(coordinator, "_m_series_path_id", path_id)
    if len(accumulator) > _PATH_MAX_POINTS:
        accumulator = accumulator[-_PATH_MAX_POINTS:]
    return accumulator


def _map_candidates(property_state: dict[str, Any]) -> tuple[str, ...]:
    candidates: list[str] = []
    map_data = property_state.get("map")
    if isinstance(map_data, dict):
        map_id = map_data.get("map_id")
        if isinstance(map_id, str) and map_id:
            candidates.append(f"map_manager_{map_id}.tar.gz")
    candidates.extend(_MAP_CANDIDATES)
    return tuple(dict.fromkeys(candidates))


def install_type_support() -> None:
    _common.register_family(
        TYPE_KEY,
        path_accumulator=_accumulate_path,
        map_candidates=_map_candidates,
    )
    _common.install_m_series_compat()
