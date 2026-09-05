"""Refresh cloud task events promptly after live mower status changes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .. import coordinator as coordinator_module
from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..mower_status import raw_robot_status

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_EVENT_RETRY_SECONDS = 5.2


def _candidate_live_state(
    self: AnthbotGenieDataUpdateCoordinator,
) -> dict[str, Any]:
    """Merge pending MQTT fragments without waiting for the one-second HA flush."""
    state = dict(self.reported_state)

    property_update = getattr(self, "_pending_live_property", None)
    if isinstance(property_update, dict) and property_update:
        state.update(property_update)

    service_update = getattr(self, "_pending_live_service", None)
    if isinstance(service_update, dict) and service_update:
        service = state.get("_service_reported")
        merged_service = dict(service) if isinstance(service, dict) else {}
        merged_service.update(service_update)
        state["_service_reported"] = merged_service

    return state


def _schedule_task_event_refresh(
    self: AnthbotGenieDataUpdateCoordinator,
    previous_status: str,
    current_status: str,
) -> None:
    """Fetch REST task events now and once more after cloud propagation."""
    active = getattr(self, "_live_task_event_refresh_task", None)
    if active is not None and not active.done():
        return

    async def runner() -> None:
        try:
            # A normal ancillary refresh may have fetched the list less than five
            # seconds ago. A real MQTT status transition must still get one fresh
            # event-list request immediately.
            self._last_task_event_download_monotonic = 0.0
            await self._async_refresh_task_events()

            # The robot shadow can change before /device/v2/code/list is updated.
            # One bounded retry catches 1036/1037/1017/1019/1022 without polling
            # the REST endpoint continuously.
            await asyncio.sleep(_EVENT_RETRY_SECONDS)
            await self._async_refresh_task_events()
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - live telemetry must keep running.
            _LOGGER.warning(
                "Task-event refresh after live status change failed for %s "
                "(%s -> %s): %s",
                self.client.serial_number,
                previous_status,
                current_status,
                err,
            )
        finally:
            if asyncio.current_task() is getattr(
                self, "_live_task_event_refresh_task", None
            ):
                self._live_task_event_refresh_task = None

    self._live_task_event_refresh_task = self.hass.async_create_background_task(
        runner(),
        f"anthbot_task_events_after_status_{self.client.serial_number}",
    )


def install_live_task_event_refresh() -> None:
    """Refresh cloud event history when MQTT reports a real mower-status change."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    # The coordinator has a duplicate activity-code set for its battery-saver
    # state machine. 1037 is the confirmed "rain stopped, task continues" event.
    coordinator_module._TASK_ACTIVITY_EVENT_CODES.add(1037)

    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow

    async def live_shadow(
        self: AnthbotGenieDataUpdateCoordinator,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        previous_status = raw_robot_status(self.reported_state)
        await previous_live(self, shadow_name, reported)

        # Genie service-shadow normalization and M-series property updates have
        # already populated the pending buffers by this point, so both model
        # families are compared through the same canonical status helper.
        current_status = raw_robot_status(_candidate_live_state(self))
        if (
            previous_status
            and current_status
            and previous_status != current_status
        ):
            _schedule_task_event_refresh(
                self,
                previous_status,
                current_status,
            )

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
