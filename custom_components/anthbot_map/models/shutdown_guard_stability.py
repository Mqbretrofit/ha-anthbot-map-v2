"""Stabilise recurring Battery Saver anti-shutdown pulses."""

from __future__ import annotations

import asyncio
import logging

from ..const import CONF_CHARGER_SWITCH
from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_SHUTDOWN_GUARD_STATE_SETTLE_SECONDS = 12.0
_SHUTDOWN_GUARD_STATE_POLL_SECONDS = 0.5


def install_shutdown_guard_state_settle() -> None:
    """Wait for the smart-plug OFF state before re-arming the next 55-minute cycle.

    Home Assistant's blocking switch service call can return before the switch
    entity itself has changed from ``on`` to ``off``. The shutdown-guard loop
    immediately reads that entity again after its one-minute pulse. Without a
    short convergence wait it can see the stale ``on`` state, clear the freshly
    stored next deadline, and stop after only one keep-awake pulse.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_set_charger = AnthbotGenieDataUpdateCoordinator._async_set_charger

    async def set_charger(
        self: AnthbotGenieDataUpdateCoordinator,
        enabled: bool,
        *,
        guard_pulse: bool = False,
    ) -> None:
        caller_is_guard = (
            asyncio.current_task() is self._battery_saver_shutdown_guard_task
        )
        await previous_set_charger(self, enabled, guard_pulse=guard_pulse)

        # Only the OFF transition that ends a guard pulse needs this wait.
        # Normal Battery Saver charger changes keep their existing behaviour.
        if (
            enabled
            or guard_pulse
            or not caller_is_guard
            or not self._battery_saver_enabled
            or self._battery_saver_shutdown_guard_due_at is None
        ):
            return

        entity_id = self.battery_saver_config.get(CONF_CHARGER_SWITCH)
        if not isinstance(entity_id, str) or not entity_id:
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + _SHUTDOWN_GUARD_STATE_SETTLE_SECONDS
        while True:
            switch_state = self.hass.states.get(entity_id)
            switch_value = (
                str(switch_state.state).strip().lower()
                if switch_state is not None
                else "unavailable"
            )
            if switch_value == "off":
                return

            remaining = deadline - loop.time()
            if remaining <= 0:
                _LOGGER.warning(
                    "Battery saver shutdown-guard OFF state did not settle for %s; "
                    "the next evaluation will reconcile the charger state",
                    self.client.serial_number,
                )
                return
            await asyncio.sleep(
                min(_SHUTDOWN_GUARD_STATE_POLL_SECONDS, remaining)
            )

    AnthbotGenieDataUpdateCoordinator._async_set_charger = set_charger
