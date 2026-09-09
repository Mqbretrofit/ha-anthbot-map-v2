"""ANTHBOT N8 task-state and mowing-history compatibility."""

from __future__ import annotations

import logging
import time
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..mower_status import raw_robot_status
from . import m_series_status as _status
from .n8_control import is_n8_model

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_RECORD_REFRESH_SECONDS = 300


def _remember_n8_task(
    self: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any] | None = None,
) -> None:
    if not is_n8_model(getattr(self.device, "model", None)):
        return
    current_state = state if isinstance(state, dict) else self.reported_state
    if not isinstance(current_state, dict):
        return
    inferred = _status._infer_task(current_state)  # noqa: SLF001
    if inferred is None:
        return
    task_type, data = inferred
    wanted = {"type": task_type, "data": data}
    if self.last_mowing_task != wanted:
        self.remember_mowing_task(task_type, data)


async def _refresh_n8_records_if_needed(
    self: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any],
) -> None:
    now = time.monotonic()
    last = float(getattr(self, "_n8_record_last_download_monotonic", 0.0) or 0.0)
    if last and now - last < _RECORD_REFRESH_SECONDS:
        records = getattr(self, "_n8_mowing_records", None)
        if isinstance(records, dict):
            self._mowing_records = records  # noqa: SLF001
            state["_mowing_records"] = records
            state["_mowing_records_error"] = getattr(
                self,
                "_n8_mowing_records_error",
                None,
            )
        return

    setattr(self, "_n8_record_last_download_monotonic", now)
    try:
        records = await _status._async_get_m_series_mowing_records(self)  # noqa: SLF001
        setattr(self, "_n8_mowing_records", records)
        setattr(self, "_n8_mowing_records_error", None)
        self._mowing_records = records  # noqa: SLF001
        self._mowing_records_error = None  # noqa: SLF001
        state["_mowing_records"] = records
        state["_mowing_records_error"] = None
        items = _status._record_items(records)  # noqa: SLF001
        state["_n8_last_mowing_record"] = items[0] if items else None
        state["_n8_mowing_records_source"] = records.get("_source")
    except Exception as err:  # noqa: BLE001 - history must not break updates.
        message = str(err)
        setattr(self, "_n8_mowing_records_error", message)
        state["_mowing_records_error"] = message
        cached = getattr(self, "_n8_mowing_records", None)
        if isinstance(cached, dict):
            self._mowing_records = cached  # noqa: SLF001
            state["_mowing_records"] = cached
        _LOGGER.warning(
            "N8 mowing records unavailable for %s: %s",
            self.client.serial_number,
            err,
        )


def _add_n8_status_aliases(state: dict[str, Any]) -> None:
    """Expose N8-specific state without changing generic public status keys."""
    status = raw_robot_status(state)
    mode_value = None
    mode = state.get("mode")
    if isinstance(mode, dict):
        mode_value = mode.get("value")
    if mode_value is None:
        robot_sta = state.get("robot_sta")
        if isinstance(robot_sta, dict):
            mode_value = robot_sta.get("value")
    normalized = str(mode_value or status or "").strip().lower()
    state["_n8_dumping"] = normalized == "dumpgrass"

    grass_state = state.get("grass_state")
    if isinstance(grass_state, dict):
        bag = grass_state.get("grass_bag_in_position")
        shield = grass_state.get("grass_shield_in_position")
        if bag is not None:
            state["_n8_grass_bag_in_position"] = bag
        if shield is not None:
            state["_n8_grass_shield_in_position"] = shield


def install_n8_status_support() -> None:
    """Install N8-only task persistence and v3 history refresh."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        await previous_live(self, shadow_name, reported)
        if is_n8_model(getattr(self.device, "model", None)):
            state = self.reported_state
            if isinstance(state, dict):
                enriched = dict(state)
                _add_n8_status_aliases(enriched)
                if enriched != state:
                    self.async_set_updated_data(enriched)
            _remember_n8_task(self)

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        if not isinstance(state, dict) or not is_n8_model(
            getattr(self.device, "model", None)
        ):
            return state
        _add_n8_status_aliases(state)
        await _refresh_n8_records_if_needed(self, state)
        _remember_n8_task(self, state)
        return state

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data


__all__ = ["install_n8_status_support"]
