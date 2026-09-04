"""ANTHBOT M9 Pro type module.

M9 Pro-specific path and map policy lives here. Shared AWS/shadow transport
remains in m_series_common.py.
"""

from typing import Any

from .base import is_m9_pro_model
from . import m_series_common as _common

TYPE_KEY = "m9_pro"
_PATH_MAX_POINTS = 50000
_MAP_CANDIDATES = ("multi_maps.tar.gz", "map_manager.tar.gz")


def matches(model: object) -> bool:
    return is_m9_pro_model(model)


def _path_points_with_metadata(decoded: dict[str, Any]) -> list[dict[str, Any]]:
    """Return finite M9 Pro path points without dropping path metadata."""
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
    """Reuse the full path already loaded before a live M9 Pro delta arrives."""
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
    """Merge an M9 Pro curpath delta at its absolute ``start`` index.

    Real M9 Pro data can publish only the tail of a much longer path. For
    example a 12-point packet with start=19652 belongs at positions
    19652..19663 of an already-known 19664-point path; treating that packet as
    a complete path makes the visible mowing trail disappear.
    """
    del packet_points  # use decoded points so type/clean_time are retained

    packet = _path_points_with_metadata(decoded)
    path_id = decoded.get("path_id")
    previous_path_id = getattr(coordinator, "_m_series_path_id", None)

    try:
        start = int(decoded.get("start", 0) or 0)
    except (TypeError, ValueError):
        start = 0
    start = max(0, start)

    accumulator = _bootstrap_existing_path(coordinator)

    # A genuinely new path that begins at zero is a new mowing/mapping task.
    if previous_path_id is not None and previous_path_id != path_id and start == 0:
        accumulator = []

    if packet:
        if start == 0:
            # Full snapshot / start of a new task.
            accumulator = list(packet)
        elif accumulator:
            if start <= len(accumulator):
                end = start + len(packet)
                if end <= len(accumulator):
                    accumulator[start:end] = packet
                else:
                    accumulator[start:] = packet
            else:
                # We have a gap because HA started after the mower session.
                # Do not fabricate coordinates for the missing range; retain
                # the known prefix and append the newest usable tail.
                accumulator.extend(packet)
        else:
            # No historical/full path is available yet. Keep the live packet
            # rather than showing nothing; a later full path can replace it.
            accumulator = list(packet)

    setattr(coordinator, "_m_series_path_id", path_id)

    # Keep enough points for a complete M9 Pro mowing session; the previous
    # 5000-point limit could truncate a 19k+ point path even when decoding was
    # otherwise correct.
    if len(accumulator) > _PATH_MAX_POINTS:
        accumulator = accumulator[-_PATH_MAX_POINTS:]
    return accumulator


def _map_candidates(property_state: dict[str, Any]) -> tuple[str, ...]:
    """M9 Pro map archive candidates, kept separate from other model families."""
    candidates: list[str] = []
    map_data = property_state.get("map")
    if isinstance(map_data, dict):
        map_id = map_data.get("map_id")
        if isinstance(map_id, str) and map_id:
            candidates.append(f"map_manager_{map_id}.tar.gz")
    candidates.extend(_MAP_CANDIDATES)
    return tuple(dict.fromkeys(candidates))


def install_type_support() -> None:
    """Register M9 Pro with its own path and map policies."""
    _common.register_family(
        TYPE_KEY,
        path_accumulator=_accumulate_path,
        map_candidates=_map_candidates,
    )
    _common.install_m_series_compat()
