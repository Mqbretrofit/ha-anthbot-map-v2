"""ANTHBOT N8 mowing-path assembly using the proven MGS path decoder."""

from __future__ import annotations

from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from . import m_series_legacy as _legacy
from . import m_series_path as _path
from .n8_control import is_n8_model

_INSTALLED = False


def _attach_n8(
    self: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any],
) -> dict[str, Any]:
    if not is_n8_model(getattr(self.device, "model", None)):
        return state

    _path._ingest(self, state.get("_path_definition"), live=False)  # noqa: SLF001
    definition = _path._merged(self)  # noqa: SLF001
    if definition is None:
        return state

    result = dict(state)
    points = definition["_path_points"]
    no_go_check = _path._update_no_go_check(self, definition, state)  # noqa: SLF001
    self._path_definition = definition  # noqa: SLF001
    self._history_path_source = "n8_curpath"  # noqa: SLF001
    result["_path_definition"] = definition
    result["_history_path_source"] = "n8_curpath"
    result["_no_go_path_check"] = no_go_check
    result["path"] = points
    result["mowed_path"] = points
    result["cloud_path"] = points

    latest = points[-1]
    pose = _path._valid_pose(result.get("pose")) or {}  # noqa: SLF001
    pose["x"] = float(latest["x"])
    pose["y"] = float(latest["y"])
    heading = _path._heading(definition.get("angle"))  # noqa: SLF001
    if heading is not None:
        pose["heading"] = heading
    result["pose"] = pose
    result["cur_pose"] = pose
    self._n8_last_pose = pose
    return result


def install_n8_path_support() -> None:
    """Install N8-only live/path history assembly without widening M-series guards."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__
    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        if is_n8_model(getattr(self.device, "model", None)):
            # Reuse the proven assembler helpers on an N8 coordinator. These
            # attribute names are coordinator-local and never mix devices.
            self._m_series_test4_points = {}
            self._m_series_test4_path_id = None
            self._m_series_test4_live_path_id = None
            self._m_series_test4_latest_angle = None
            self._m_series_test4_latest_angle_index = -1
            self._m_series_no_go_check_signature = None
            self._m_series_no_go_check = None

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        if is_n8_model(getattr(self.device, "model", None)) and isinstance(reported, dict):
            decoded = _legacy._decode_live_curpath(reported.get("curpath"))  # noqa: SLF001
            if isinstance(decoded, dict):
                _path._ingest(self, getattr(self, "_path_definition", None), live=False)  # noqa: SLF001
                _path._ingest(self, decoded, live=True)  # noqa: SLF001
                merged = _path._merged(self)  # noqa: SLF001
                if merged is not None:
                    forwarded = dict(reported)
                    forwarded.pop("curpath", None)
                    points = merged["_path_points"]
                    check_state = dict(getattr(self, "reported_state", {}) or {})
                    check_state.update(reported)
                    no_go_check = _path._update_no_go_check(  # noqa: SLF001
                        self,
                        merged,
                        check_state,
                    )
                    forwarded["_path_definition"] = merged
                    forwarded["_history_path_source"] = "n8_curpath"
                    forwarded["_no_go_path_check"] = no_go_check
                    forwarded["path"] = points
                    forwarded["mowed_path"] = points
                    forwarded["cloud_path"] = points
                    latest = points[-1]
                    pose = (
                        _path._valid_pose(forwarded.get("pose"))  # noqa: SLF001
                        or _path._valid_pose(  # noqa: SLF001
                            getattr(self, "reported_state", {}).get("pose")
                        )
                        or {}
                    )
                    pose["x"] = float(latest["x"])
                    pose["y"] = float(latest["y"])
                    angle = _path._heading(merged.get("angle"))  # noqa: SLF001
                    if angle is not None:
                        pose["heading"] = angle
                    forwarded["pose"] = pose
                    forwarded["cur_pose"] = pose
                    reported = forwarded
        await previous_live(self, shadow_name, reported)

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        return _attach_n8(self, state)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data


__all__ = ["install_n8_path_support"]
