"""Native Home Assistant events for Anthbot mower lifecycle changes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ERROR_CODE_DESCRIPTIONS
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .mower_status import as_int, mower_activity_name, raw_robot_status
from .schedule_engine import (
    EVENT_OVERRIDE_CHANGED,
    EVENT_SCHEDULE_ERROR,
    EVENT_SCHEDULE_SKIPPED,
    EVENT_SCHEDULE_TRIGGERED,
)
from .task_events import RAIN_RETURN_CODE, TASK_FINISHED_CODE, task_event_code

EVENT_TYPES = (
    "mowing_started",
    "mowing_completed",
    "stuck",
    "error",
    "rain_hold",
    "docked",
    "schedule_triggered",
    "schedule_skipped",
    "schedule_error",
    "override_changed",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(AnthbotMowerEvent(coordinator) for coordinator in coordinators)


def _snapshot(state: dict[str, Any]) -> dict[str, Any]:
    raw = raw_robot_status(state)
    return {
        "activity": mower_activity_name(state),
        "raw_status": raw,
        "error_code": as_int(state.get("err_code")),
        "task_event_code": task_event_code(state.get("_task_events")),
    }


class AnthbotMowerEvent(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], EventEntity
):
    """Emit automation-friendly events instead of requiring status parsing."""

    _attr_has_entity_name = True
    _attr_name = "Mower events"
    _attr_translation_key = "mower_events"
    _attr_event_types = list(EVENT_TYPES)

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_mower_events"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )
        self._previous = _snapshot(coordinator.reported_state)

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        payload = {
            "model": self.coordinator.device.model,
            "raw_status": raw_robot_status(self.coordinator.reported_state),
            **data,
        }
        self._trigger_event(event_type, payload)

    @callback
    def _handle_schedule_bus_event(self, event: Event) -> None:
        if event.data.get("serial_number") != self.coordinator.client.serial_number:
            return
        event_type = event.event_type.removeprefix(f"{DOMAIN}_")
        if event_type not in EVENT_TYPES:
            return
        self._emit(
            event_type,
            {
                key: value
                for key, value in event.data.items()
                if key != "serial_number"
            },
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for event_type in (
            EVENT_SCHEDULE_TRIGGERED,
            EVENT_SCHEDULE_SKIPPED,
            EVENT_SCHEDULE_ERROR,
            EVENT_OVERRIDE_CHANGED,
        ):
            self.async_on_remove(
                self.hass.bus.async_listen(event_type, self._handle_schedule_bus_event)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        current = _snapshot(self.coordinator.reported_state)
        previous = self._previous
        self._previous = current

        error_code = current["error_code"]
        if error_code not in (None, 0) and error_code != previous["error_code"]:
            description = ERROR_CODE_DESCRIPTIONS.get(
                error_code, f"Unknown error ({error_code})"
            )
            lowered = description.casefold()
            event_type = (
                "stuck"
                if any(
                    token in lowered
                    for token in ("stuck", "blocked", "trapped", "stall", "jammed")
                )
                else "error"
            )
            self._emit(
                event_type,
                {"error_code": error_code, "description": description},
            )

        task_code = current["task_event_code"]
        if task_code != previous["task_event_code"]:
            if task_code == TASK_FINISHED_CODE:
                self._emit("mowing_completed", {"task_event_code": task_code})
            elif task_code in {RAIN_RETURN_CODE, 1038}:
                self._emit("rain_hold", {"task_event_code": task_code})

        activity = current["activity"]
        if activity != previous["activity"]:
            if activity == "mowing":
                self._emit("mowing_started", {})
            elif activity == "docked":
                self._emit("docked", {})

        super()._handle_coordinator_update()
