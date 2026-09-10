"""Pure helpers for the statically proven N8/MGS03 dumping-area wire format.

These builders deliberately do not publish commands. Public Home Assistant dump-area
editing remains disabled until real-hardware add/edit/delete captures confirm the
persisted map-manager behavior and placement validation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

DUMP_AREA_ID_MIN = 500
DUMP_AREA_ID_MAX = 599
REMOTE_DUMP_STATES = {
    "build_dump_init",
    "build_dump_continue",
    "build_dump_finish",
    "build_dump_set",
}


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _dump_id(value: object) -> int:
    area_id = _integer(value, field="dump area id")
    if area_id < DUMP_AREA_ID_MIN or area_id > DUMP_AREA_ID_MAX:
        raise ValueError(
            f"dump area id must be {DUMP_AREA_ID_MIN}..{DUMP_AREA_ID_MAX}"
        )
    return area_id


def _vertices(value: Sequence[Sequence[object]]) -> list[list[int]]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("dump area must contain exactly four vertices")
    result: list[list[int]] = []
    for index, point in enumerate(value):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError(f"vertex {index} must be an [x_mm, y_mm] pair")
        result.append(
            [
                _integer(point[0], field=f"vertex {index} x_mm"),
                _integer(point[1], field=f"vertex {index} y_mm"),
            ]
        )
    return result


def build_dump_area(
    area_id: int,
    vertexs: Sequence[Sequence[object]],
    *,
    remote: bool = False,
    eid: int = -1,
    disable: bool = False,
    warning_type: int = 0,
) -> dict[str, Any]:
    """Return one exact app-style dumping-area object.

    Coordinates are already-converted map/world millimetres. This helper does not
    accept screen pixels, latitude/longitude or apply map transforms.
    """
    normalized_id = _dump_id(area_id)
    if not isinstance(remote, bool):
        raise ValueError("remote must be a boolean")
    if not isinstance(disable, bool):
        raise ValueError("disable must be a boolean")
    return {
        "vertexs": _vertices(vertexs),
        "id": normalized_id,
        "grassId": normalized_id,
        "eid": _integer(eid, field="eid"),
        "remote": remote,
        "disable": disable,
        "warningType": _integer(warning_type, field="warningType"),
    }


def build_area_set_data(
    changed_areas: Iterable[dict[str, Any]],
    deleted_ids: Iterable[int],
) -> dict[str, Any]:
    """Return the proven `area_set` data object for dump-area edits/deletes."""
    areas = [dict(area) for area in changed_areas]
    for area in areas:
        _dump_id(area.get("id"))
        if area.get("grassId") != area.get("id"):
            raise ValueError("dump area grassId must equal id")
        _vertices(area.get("vertexs"))
    return {
        "dump_grass_areas": areas,
        "delete_dump_areas": [_dump_id(value) for value in deleted_ids],
    }


def build_remote_dump_data(
    state: str,
    areas: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Return one proven `ctl_building_dump` data object."""
    if state not in REMOTE_DUMP_STATES:
        raise ValueError(f"unsupported remote dump state: {state}")
    normalized = [dict(area) for area in areas]
    if state == "build_dump_set":
        if not normalized:
            raise ValueError("build_dump_set requires at least one dumping area")
        for area in normalized:
            _dump_id(area.get("id"))
            if area.get("grassId") != area.get("id"):
                raise ValueError("dump area grassId must equal id")
            if area.get("remote") is not True:
                raise ValueError("remote dumping area must set remote=true")
            _vertices(area.get("vertexs"))
        return {"dump_grass_areas": normalized, "state": state}
    if normalized:
        raise ValueError(f"{state} does not carry dumping-area geometry")
    return {"state": state}


__all__ = [
    "DUMP_AREA_ID_MAX",
    "DUMP_AREA_ID_MIN",
    "REMOTE_DUMP_STATES",
    "build_area_set_data",
    "build_dump_area",
    "build_remote_dump_data",
]
