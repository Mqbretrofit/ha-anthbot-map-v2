"""M-series mowing target/status persistence for the dashboard."""

from __future__ import annotations

from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..mower_status import raw_robot_status
from ..zones import active_manual_zone_ids

_INSTALLED = False


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _infer_task(state: dict[str, Any]) -> tuple[str, Any] | None:
    status = raw_robot_status(state)
    if status == "globalmowing":
        return "full", None
    if status == "bordermowing":
        return "edge", None
    if status == "nestmowing":
        return "dock_edge", None
    if status == "zonemowing":
        zone_ids = active_manual_zone_ids(state)
        if zone_ids:
            return "manual_zone", {"id": zone_ids}
    if status == "regionmowing":
        # M-series region mowing is the app's automatic-zone mode.
        return "auto_zone", None
    return None


def _remember_if_changed(self: AnthbotGenieDataUpdateCoordinator) -> None:
    if not _is_m_series(getattr(self.device, "model", None)):
        return
    state = self.reported_state
    if not isinstance(state, dict):
        return
    inferred = _infer_task(state)
    if inferred is None:
        return
    task_type, data = inferred
    current = self.last_mowing_task
    wanted = {"type": task_type, "data": data}
    if current == wanted:
        return
    # Use the existing beta3 persistence path, but only when the inferred task
    # actually changes, so live MQTT packets do not cause repeated writes.
    self.remember_mowing_task(task_type, data)


def install_m_series_status_support() -> None:
    """Persist the real M-series mowing target from live/property status."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        await previous_live(self, shadow_name, reported)
        _remember_if_changed(self)

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        _remember_if_changed(self)
        return self.reported_state if isinstance(self.reported_state, dict) else state

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
