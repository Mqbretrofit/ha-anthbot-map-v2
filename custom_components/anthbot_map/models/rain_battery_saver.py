"""Rain-safe Battery Saver behavior shared by Genie and M-series mowers."""

from __future__ import annotations

import asyncio
from typing import Any

from .. import coordinator as coordinator_module
from ..const import CONF_RESUME_LEVEL, CONF_SHARED_RTK_POWER
from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..task_events import task_event_items

_INSTALLED = False
_RAIN_PROTECTION_EVENT_CODE = 1038
_RESUME_RAIN_VERIFY_SECONDS = 5.2


def _coerce_event_code(value: Any) -> int | None:
    """Return an event code from scalar or shadow-style wrapped values."""
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _live_rain_protection(self: AnthbotGenieDataUpdateCoordinator) -> bool:
    """Return whether the live shadow explicitly rejected work because of rain."""
    return (
        _coerce_event_code(self.reported_state.get("event_code"))
        == _RAIN_PROTECTION_EVENT_CODE
    )


def _current_rain_hold_signal(self: AnthbotGenieDataUpdateCoordinator) -> bool:
    """Use the fast live 1038 signal or the task-cycle 1036/1038 classifier."""
    return _live_rain_protection(self) or self._battery_saver_task_signal(
        self._task_events
    ) == "rain_return"


def install_rain_battery_saver_safety() -> None:
    """Keep Battery Saver and Shutdown Guard safe across rain interruptions."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_set_enabled = (
        AnthbotGenieDataUpdateCoordinator.async_set_battery_saver_enabled
    )
    previous_maintain_idle_charge = (
        AnthbotGenieDataUpdateCoordinator._async_maintain_idle_charge
    )
    previous_refresh_task_events = (
        AnthbotGenieDataUpdateCoordinator._async_refresh_task_events
    )
    previous_evaluate = AnthbotGenieDataUpdateCoordinator._async_evaluate_battery_saver

    def task_signal(payload: Any) -> str | None:
        """Classify 1038 in the same newest-first task-cycle order as 1036."""
        for event in task_event_items(payload):
            code = _coerce_event_code(event.get("code"))
            if code == coordinator_module._TASK_FINISHED_EVENT_CODE:
                return "completed"
            if code in {
                coordinator_module._RAIN_RETURN_EVENT_CODE,
                _RAIN_PROTECTION_EVENT_CODE,
            }:
                return "rain_return"
            if code == coordinator_module._LOW_BATTERY_RETURN_EVENT_CODE:
                return "low_battery_return"
            if code in coordinator_module._TASK_ACTIVITY_EVENT_CODES:
                return "active"
        return None

    async def set_enabled(
        self: AnthbotGenieDataUpdateCoordinator, enabled: bool
    ) -> None:
        await previous_set_enabled(self, enabled)
        if (
            enabled
            and self._battery_saver_phase == "initial_charge"
            and _current_rain_hold_signal(self)
        ):
            self._battery_saver_phase = "rain_hold"
            await self._async_save_battery_saver_state()
            if self.reported_state:
                state = dict(self.reported_state)
                state["_battery_saver_phase"] = self._battery_saver_phase
                self.async_set_updated_data(state)

    async def maintain_idle_charge(
        self: AnthbotGenieDataUpdateCoordinator, battery: int
    ) -> None:
        if (
            self._battery_saver_phase == "rain_hold"
            and self.battery_saver_config[CONF_SHARED_RTK_POWER]
        ):
            # If the smart plug also powers the RTK base, switching it off while
            # waiting for rain to clear can prevent the mower's firmware-driven
            # automatic resume. Functional resume takes priority over the upper
            # charge limit in this specific shared-supply case.
            await self._async_set_charger(True)
            return
        # With separate RTK power, keep the normal charge hysteresis. When the
        # plug is OFF the existing 55+1 minute Shutdown Guard remains active.
        await previous_maintain_idle_charge(self, battery)

    async def refresh_task_events(self: AnthbotGenieDataUpdateCoordinator) -> None:
        """Skip redundant REST event polling while rain hold is stably docked."""
        if (
            self._battery_saver_enabled
            and self._battery_saver_phase == "rain_hold"
            and self._robot_status(self.reported_state)
            in coordinator_module._DOCKED_STATUS_VALUES
        ):
            # Stable docked rain-hold coordinator updates used to call the REST
            # event list every ~5 seconds. Real rain-stop/resume transitions are
            # still detected immediately by the live-status refresh path once the
            # mower leaves the docked phase. Normal coordinator refreshes also
            # continue to fetch the task-event list directly as a cloud fallback.
            return
        await previous_refresh_task_events(self)

    async def evaluate(self: AnthbotGenieDataUpdateCoordinator) -> None:
        config = self.battery_saver_config
        status = self._robot_status(self.reported_state)
        battery = self._battery_percentage(self.reported_state)
        resume_candidate = bool(
            self._battery_saver_enabled
            and self._battery_saver_phase == "recovery_charge"
            and status in coordinator_module._DOCKED_STATUS_VALUES
            and battery is not None
            and battery >= config[CONF_RESUME_LEVEL]
            and self.last_mowing_task is not None
        )

        if resume_candidate:
            # Refresh immediately before a low-battery resume. This catches a
            # 1036/1038 that arrived while the mower was charging and avoids an
            # unnecessary mow_continue whenever the cloud already knows rain is
            # blocking the task.
            self._last_task_event_download_monotonic = 0.0
            await self._async_refresh_task_events()
            if _current_rain_hold_signal(self):
                self._battery_saver_phase = "rain_hold"
                await self._async_save_battery_saver_state()

        await previous_evaluate(self)

        if not resume_candidate or self._battery_saver_phase != "mowing":
            return

        # 1038 is typically produced because the first resume attempt was
        # rejected by rain protection, so it cannot always be known before the
        # command. Verify once after cloud propagation; if 1038 appears, move to
        # rain_hold and let the mower firmware decide when it may resume.
        await asyncio.sleep(_RESUME_RAIN_VERIFY_SECONDS)
        self._last_task_event_download_monotonic = 0.0
        await self._async_refresh_task_events()
        if not _current_rain_hold_signal(self):
            return

        self._battery_saver_phase = "rain_hold"
        await self._async_save_battery_saver_state()
        current_status = self._robot_status(self.reported_state)
        current_battery = self._battery_percentage(self.reported_state)
        if current_status in coordinator_module._DOCKED_STATUS_VALUES:
            if current_battery is not None:
                await self._async_maintain_idle_charge(current_battery)
        else:
            await self._async_set_charger(True)

    AnthbotGenieDataUpdateCoordinator._battery_saver_task_signal = staticmethod(
        task_signal
    )
    AnthbotGenieDataUpdateCoordinator.async_set_battery_saver_enabled = set_enabled
    AnthbotGenieDataUpdateCoordinator._async_maintain_idle_charge = (
        maintain_idle_charge
    )
    AnthbotGenieDataUpdateCoordinator._async_refresh_task_events = refresh_task_events
    AnthbotGenieDataUpdateCoordinator._async_evaluate_battery_saver = evaluate
