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


def _simple_reported_value(value: Any) -> Any:
    """Unwrap the common N8 {value: ...} report envelope when present."""
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def _add_n8_status_aliases(state: dict[str, Any]) -> None:
    """Expose N8-specific state without changing other mower-family routing."""
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

    # An M9 Pro shared-schema capture reports physical-panel Child Lock under
    # device_config.child_lock_switch. The 2.15.16 bundle still does not prove
    # this as the N8 write key, so only mirror it when an actual N8 state
    # contains the field. Keep it separate from ui_lock, whose semantics are
    # the generic app/device command lock.
    device_config = state.get("device_config")
    if isinstance(device_config, dict):
        child_lock = device_config.get("child_lock_switch")
        if child_lock is not None:
            state["_n8_child_lock"] = child_lock

    # M9 Pro shared-schema evidence also exposes ctl_rtk_base acknowledgement
    # fields. Static 2.15.16 MGS analysis independently proves the 1/2/3 RTK
    # mode command mapping, but the report path still needs a real N8 capture.
    # Mirror these values only when they are genuinely present in N8 state.
    rtk_base_control = state.get("ctl_rtk_base")
    if isinstance(rtk_base_control, dict):
        rtk_base_state = rtk_base_control.get("rtk_base_state")
        nrtk_base_sdk = rtk_base_control.get("nrtk_base_sdk")
        if rtk_base_state is not None:
            state["_n8_rtk_base_state"] = rtk_base_state
        if nrtk_base_sdk is not None:
            state["_n8_nrtk_base_sdk"] = nrtk_base_sdk

    # Current MGS 2.15.16 reads global cutting height as the direct reported
    # `cutter_height` property, while the existing shared HA number reads
    # `param_set.cutter_height`. Mirror only this N8 field so the established
    # entity remains readable without changing Genie/M5/M9/M9 Pro behavior.
    cutter_height = _simple_reported_value(state.get("cutter_height"))
    if isinstance(cutter_height, (int, float)):
        existing = state.get("param_set")
        params = dict(existing) if isinstance(existing, dict) else {}
        if params.get("cutter_height") != cutter_height:
            params["cutter_height"] = cutter_height
            state["param_set"] = params
        state["_n8_cutter_height"] = cutter_height


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
