"""Native lawn mower platform for Anthbot Genie."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AnthbotGenieApiError
from .commands import async_prepare_cloud_connection, async_start_mowing
from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .mower_status import mower_activity_name, raw_robot_status

_ACTIVITY_BY_NAME = {
    "mowing": LawnMowerActivity.MOWING,
    "docked": LawnMowerActivity.DOCKED,
    "paused": LawnMowerActivity.PAUSED,
    "returning": LawnMowerActivity.RETURNING,
    "error": LawnMowerActivity.ERROR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a native lawn mower entity for every Anthbot mower."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(AnthbotLawnMowerEntity(coordinator) for coordinator in coordinators)


class AnthbotLawnMowerEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], LawnMowerEntity
):
    """Represent an Anthbot mower as a native Home Assistant lawn mower."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        serial_number = coordinator.client.serial_number
        self._attr_unique_id = f"{serial_number}_mower"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def activity(self) -> LawnMowerActivity | None:
        """Return the current native mower activity."""
        activity_name = mower_activity_name(self.coordinator.reported_state)
        return _ACTIVITY_BY_NAME.get(activity_name)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful Anthbot metadata on the native entity."""
        return {
            "serial_number": self.coordinator.client.serial_number,
            "raw_status": raw_robot_status(self.coordinator.reported_state),
        }

    async def _async_refresh_after_command(self) -> None:
        """Refresh the mower state after a command."""
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def async_start_mowing(self) -> None:
        """Start full-lawn mowing."""
        started = await async_start_mowing(self.coordinator, app_state=1)
        if not started:
            raise AnthbotGenieApiError("The mower did not confirm the start command")

    async def async_pause(self) -> None:
        """Stop the current Anthbot task through Home Assistant's pause action."""
        if not await async_prepare_cloud_connection(self.coordinator):
            raise AnthbotGenieApiError(
                "The mower did not confirm its cloud connection; stop command was not sent"
            )
        await self.coordinator.client.async_publish_service_command(cmd="stop_all_tasks")
        await self._async_refresh_after_command()

    async def async_dock(self) -> None:
        """Return the mower to its charging dock."""
        if not await async_prepare_cloud_connection(self.coordinator):
            raise AnthbotGenieApiError(
                "The mower did not confirm its cloud connection; dock command was not sent"
            )
        await self.coordinator.client.async_publish_service_command(cmd="charge_start")
        await self._async_refresh_after_command()
