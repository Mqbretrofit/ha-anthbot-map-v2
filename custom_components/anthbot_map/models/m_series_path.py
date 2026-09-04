"""Verified test4 M-series mowing-path assembly layered on the rebuild base."""

from __future__ import annotations

import math
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from . import m_series_legacy as _legacy

_INSTALLED = False
_MAX_POINTS = 20000


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _points(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for point in value:
        if isinstance(point, dict):
            x, y = point.get("x"), point.get("y")
            normalized = dict(point)
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            x, y = point[0], point[1]
            normalized = {}
        else:
            continue
        try:
            normalized["x"] = float(x)
            normalized["y"] = float(y)
        except (TypeError, ValueError):
            continue
        result.append(normalized)
    return result


def _start(definition: dict[str, Any]) -> int:
    value = definition.get("start", definition.get("path_start", 0))
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _heading(value: Any) -> float | None:
    try:
        angle = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(angle):
        return None
    # Exact test4 M9/M9 Pro convention.
    return 90.0 - math.degrees(angle / 1000.0)


def _valid_pose(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    try:
        x = float(value.get("x"))
        y = float(value.get("y"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    pose = dict(value)
    pose["x"], pose["y"] = x, y
    return pose


def _ingest(self: AnthbotGenieDataUpdateCoordinator, definition: Any, *, live: bool) -> None:
    if not isinstance(definition, dict) or definition.get("_m_series_test4_merged") is True:
        return
    path_points = _points(definition.get("_path_points"))
    if not path_points:
        return
    path_id = definition.get("path_id")
    previous_path_id = getattr(self, "_m_series_test4_path_id", None)
    live_path_id = getattr(self, "_m_series_test4_live_path_id", None)

    # test4: a delayed history file from an older mowing task must not replace
    # the currently active curpath.
    if not live and live_path_id is not None and path_id is not None and path_id != live_path_id:
        return

    indexed = getattr(self, "_m_series_test4_points", {})
    path_changed = previous_path_id is not None and path_id is not None and previous_path_id != path_id
    if not isinstance(indexed, dict) or path_changed:
        indexed = {}
        self._m_series_test4_latest_angle = None
        self._m_series_test4_latest_angle_index = -1

    start = _start(definition)
    for offset, point in enumerate(path_points):
        # Same behavior as test4: fill missing absolute slots, do not overwrite
        # an already assembled valid point.
        indexed.setdefault(start + offset, point)

    if len(indexed) > _MAX_POINTS:
        keep = sorted(indexed)[-_MAX_POINTS:]
        indexed = {index: indexed[index] for index in keep}
    self._m_series_test4_points = indexed

    if path_id is not None:
        self._m_series_test4_path_id = path_id
        if live:
            self._m_series_test4_live_path_id = path_id

    last_index = start + len(path_points) - 1
    try:
        angle = float(definition.get("angle"))
        finite = math.isfinite(angle)
    except (TypeError, ValueError):
        finite = False
        angle = 0.0
    latest_index = int(getattr(self, "_m_series_test4_latest_angle_index", -1))
    if finite and last_index >= latest_index:
        self._m_series_test4_latest_angle = angle
        self._m_series_test4_latest_angle_index = last_index
    self._m_series_test4_template = dict(definition)


def _merged(self: AnthbotGenieDataUpdateCoordinator) -> dict[str, Any] | None:
    indexed = getattr(self, "_m_series_test4_points", {})
    if not isinstance(indexed, dict) or not indexed:
        return None
    indices = sorted(indexed)
    result: list[dict[str, Any]] = []
    previous: int | None = None
    for index in indices:
        point = dict(indexed[index])
        if previous is not None and index != previous + 1:
            point["break_before"] = True
        result.append(point)
        previous = index

    template = getattr(self, "_m_series_test4_template", None)
    definition = dict(template) if isinstance(template, dict) else {}
    definition["_path_points"] = result
    definition["start"] = indices[0]
    definition["path_start"] = indices[0]
    definition["point_count"] = len(result)
    definition["declared_size"] = len(result)
    definition["path_id"] = getattr(self, "_m_series_test4_path_id", None)
    definition["_m_series_test4_merged"] = True
    definition["_m_series_first_index"] = indices[0]
    definition["_m_series_last_index"] = indices[-1]
    angle = getattr(self, "_m_series_test4_latest_angle", None)
    if angle is not None:
        definition["angle"] = angle
        result[-1]["angle"] = angle
    return definition


def _attach(self: AnthbotGenieDataUpdateCoordinator, state: dict[str, Any]) -> dict[str, Any]:
    if not _is_m_series(getattr(self.device, "model", None)):
        return state
    _ingest(self, state.get("_path_definition"), live=False)
    definition = _merged(self)
    if definition is None:
        return state
    result = dict(state)
    points = definition["_path_points"]
    self._path_definition = definition
    self._history_path_source = "m_series_curpath"
    result["_path_definition"] = definition
    result["_history_path_source"] = "m_series_curpath"
    result["path"] = points
    result["mowed_path"] = points
    result["cloud_path"] = points

    latest = points[-1]
    pose = _valid_pose(result.get("pose")) or {}
    pose["x"] = float(latest["x"])
    pose["y"] = float(latest["y"])
    heading = _heading(definition.get("angle"))
    if heading is not None:
        pose["heading"] = heading
    result["pose"] = pose
    result["cur_pose"] = pose
    self._m_series_last_pose = pose
    return result


def install_m_series_path_support() -> None:
    """Install test4 path.bin + curpath absolute-index assembly for M-series only."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__
    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        if _is_m_series(getattr(self.device, "model", None)):
            self._m_series_test4_points = {}
            self._m_series_test4_path_id = None
            self._m_series_test4_live_path_id = None
            self._m_series_test4_latest_angle = None
            self._m_series_test4_latest_angle_index = -1

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        if _is_m_series(getattr(self.device, "model", None)) and isinstance(reported, dict):
            decoded = _legacy._decode_live_curpath(reported.get("curpath"))
            if isinstance(decoded, dict):
                _ingest(self, getattr(self, "_path_definition", None), live=False)
                _ingest(self, decoded, live=True)
                merged = _merged(self)
                if merged is not None:
                    forwarded = dict(reported)
                    # Prevent the older compatibility layer from re-decoding
                    # the short chunk and replacing the test4 assembled trail.
                    forwarded.pop("curpath", None)
                    points = merged["_path_points"]
                    forwarded["_path_definition"] = merged
                    forwarded["_history_path_source"] = "m_series_curpath"
                    forwarded["path"] = points
                    forwarded["mowed_path"] = points
                    forwarded["cloud_path"] = points
                    latest = points[-1]
                    pose = _valid_pose(forwarded.get("pose")) or _valid_pose(getattr(self, "reported_state", {}).get("pose")) or {}
                    pose["x"] = float(latest["x"])
                    pose["y"] = float(latest["y"])
                    angle = _heading(merged.get("angle"))
                    if angle is not None:
                        pose["heading"] = angle
                    forwarded["pose"] = pose
                    forwarded["cur_pose"] = pose
                    reported = forwarded
        await previous_live(self, shadow_name, reported)

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        return _attach(self, state)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
