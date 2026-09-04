"""ANTHBOT M9 Pro type module.

M9 Pro-specific path and map policy lives here. Shared AWS/shadow transport
remains in m_series_common.py.
"""

from typing import Any

from .base import is_m9_pro_model
from . import m_series_common as _common

TYPE_KEY = "m9_pro"
_PATH_MAX_POINTS = 5000
_MAP_CANDIDATES = ("multi_maps.tar.gz", "map_manager.tar.gz")


def matches(model: object) -> bool:
    return is_m9_pro_model(model)


def _accumulate_path(
    coordinator: Any,
    decoded: dict[str, Any],
    packet_points: list[dict[str, float]],
) -> list[dict[str, float]]:
    """M9 Pro live-curpath accumulation policy from the working beta3 behavior."""
    path_id = decoded.get("path_id")
    accumulator = getattr(coordinator, "_m_series_path_accumulator", [])
    previous_path_id = getattr(coordinator, "_m_series_path_id", None)

    if not isinstance(accumulator, list) or previous_path_id != path_id:
        accumulator = list(packet_points)
        setattr(coordinator, "_m_series_path_id", path_id)
    elif packet_points:
        if not accumulator:
            accumulator = list(packet_points)
        elif _common.point_distance(accumulator[-1], packet_points[-1]) > 0:
            accumulator.append(packet_points[-1])

    return accumulator[-_PATH_MAX_POINTS:]


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
