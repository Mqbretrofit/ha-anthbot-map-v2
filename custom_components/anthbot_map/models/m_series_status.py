"""M-series mowing target/status and cloud-history compatibility."""

from __future__ import annotations

import logging
import time
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..mower_status import raw_robot_status
from ..zones import active_manual_zone_ids

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_M_SERIES_RECORD_REFRESH_SECONDS = 300


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _infer_task(state: dict[str, Any]) -> tuple[str, Any] | None:
    """Infer the active task from the M-series live/property status."""
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
        return "auto_zone", None
    return None


def _record_items(records: object) -> list[dict[str, Any]]:
    """Return normalized record dictionaries from v3 or legacy containers."""
    if not isinstance(records, dict):
        return []
    value = records.get("data")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("data", "list", "records", "items", "rows"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _infer_task_from_record(record: dict[str, Any]) -> tuple[str, Any] | None:
    """Interpret a completed M-series cloud-history record.

    This helper is kept for diagnostics/history-mode work only.  Completed
    records must never recreate ``last_mowing_task`` because Stop explicitly
    deletes the resumable task.  Captured M9 Pro records use mow_mode=0 for
    full-area mowing; other mode values are not guessed until captured.
    """
    for key in ("zone_ids", "zones", "area_ids"):
        value = record.get(key)
        if isinstance(value, list) and value:
            return "manual_zone", {"id": value}

    for key in ("zone_id", "area_id"):
        value = record.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return "manual_zone", {"id": [value]}

    mow_mode = record.get("mow_mode")
    if mow_mode == 0 or str(mow_mode).strip() == "0":
        return "full", None
    return None


def _remember_if_changed(
    self: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any] | None = None,
) -> None:
    if not _is_m_series(getattr(self.device, "model", None)):
        return
    current_state = state if isinstance(state, dict) else self.reported_state
    if not isinstance(current_state, dict):
        return

    # Only a currently active/live mower state may create or update the
    # resumable task.  Never fall back to the newest completed cloud-history
    # record here: after Stop that record still exists and would immediately
    # resurrect a task that async_clear_last_mowing_task() just deleted.
    inferred = _infer_task(current_state)
    if inferred is None:
        return

    task_type, data = inferred
    current = self.last_mowing_task
    wanted = {"type": task_type, "data": data}
    if current == wanted:
        return
    self.remember_mowing_task(task_type, data)


async def _async_get_m_series_mowing_records(
    self: AnthbotGenieDataUpdateCoordinator,
    *,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """Fetch M5/M9 completed mowing records from the confirmed v3 endpoint."""
    account = self.account_client
    session = getattr(account, "_session", None)
    host = getattr(account, "_host", None)
    headers = getattr(account, "_auth_headers", None)
    if session is None or not isinstance(host, str) or not host:
        raise RuntimeError("Anthbot account client is not ready")

    url = f"https://{host}/api/v1/device/v3/record/list"
    params = {
        "sn": self.client.serial_number,
        "pagenum": page,
        "pagesize": page_size,
    }
    async with session.get(url, headers=headers, params=params, timeout=15) as response:
        if response.status != 200:
            body = await response.text()
            raise RuntimeError(
                f"M-series mowing records failed ({response.status}): {body[:300]}"
            )
        payload = await response.json(content_type=None)

    if not isinstance(payload, dict) or payload.get("code") != 0:
        code = payload.get("code") if isinstance(payload, dict) else "n/a"
        raise RuntimeError(f"Invalid M-series mowing record response (code={code})")

    data = payload.get("data")
    if isinstance(data, dict):
        normalized = dict(data)
    elif isinstance(data, list):
        normalized = {"data": data}
    else:
        normalized = {"data": []}

    normalized["_source"] = "api/v1/device/v3/record/list"
    return normalized


async def _refresh_m_series_records_if_needed(
    self: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any],
) -> None:
    if not _is_m_series(getattr(self.device, "model", None)):
        return

    now = time.monotonic()
    last = float(getattr(self, "_m_series_record_last_download_monotonic", 0.0) or 0.0)
    if last and now - last < _M_SERIES_RECORD_REFRESH_SECONDS:
        records = getattr(self, "_m_series_mowing_records", None)
        if isinstance(records, dict):
            self._mowing_records = records
            state["_mowing_records"] = records
            state["_mowing_records_error"] = getattr(
                self, "_m_series_mowing_records_error", None
            )
        return

    setattr(self, "_m_series_record_last_download_monotonic", now)
    try:
        records = await _async_get_m_series_mowing_records(self)
        setattr(self, "_m_series_mowing_records", records)
        setattr(self, "_m_series_mowing_records_error", None)
        self._mowing_records = records
        self._mowing_records_error = None
        state["_mowing_records"] = records
        state["_mowing_records_error"] = None
        items = _record_items(records)
        state["_m_series_last_mowing_record"] = items[0] if items else None
        state["_m_series_mowing_records_source"] = records.get("_source")
        _LOGGER.debug(
            "Loaded %s M-series mowing records for %s",
            len(items),
            self.client.serial_number,
        )
    except Exception as err:  # noqa: BLE001 - history must never break mower updates.
        message = str(err)
        setattr(self, "_m_series_mowing_records_error", message)
        state["_mowing_records_error"] = message
        _LOGGER.warning(
            "M-series mowing records unavailable for %s: %s",
            self.client.serial_number,
            err,
        )
        records = getattr(self, "_m_series_mowing_records", None)
        if isinstance(records, dict):
            self._mowing_records = records
            state["_mowing_records"] = records


def install_m_series_status_support() -> None:
    """Add M-series live target persistence, cloud history and battery compatibility."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data
    previous_robot_status = AnthbotGenieDataUpdateCoordinator._robot_status

    async def live_shadow(self, shadow_name: str, reported: dict[str, Any]) -> None:
        await previous_live(self, shadow_name, reported)
        _remember_if_changed(self)

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        if not isinstance(state, dict):
            return state
        if _is_m_series(getattr(self.device, "model", None)):
            await _refresh_m_series_records_if_needed(self, state)
            _remember_if_changed(self, state)
        return state

    def robot_status(self, data: dict[str, Any]) -> str:
        """Treat M-series shutdown-on-dock as standby for battery-saver logic only.

        M5/M9/M9 Pro can report ``shutdown`` while physically docked after the
        smart-plug charger has been switched off. The beta3 shutdown guard
        otherwise interprets that as leaving the dock and cancels its 55+1
        minute keep-awake cycle. The coordinator's private _robot_status helper
        is only used by the battery-saver state machine, so normalize that one
        M-series state here without changing the public mower status sensor.
        """
        status = previous_robot_status(data)
        if _is_m_series(getattr(self.device, "model", None)) and status == "shutdown":
            return "standby"
        return status

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
    AnthbotGenieDataUpdateCoordinator._robot_status = robot_status
