"""Select platform for Anthbot Genie settings."""

from __future__ import annotations

import asyncio

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator

_SPEED_TO_RAW: dict[str, int] = {
    "0.2 m/s": 200,
    "0.3 m/s": 300,
    "0.4 m/s": 400,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot select entities from a config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotMowingSpeedSelect(coordinator) for coordinator in coordinators
    )


class AnthbotMowingSpeedSelect(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SelectEntity
):
    """Anthbot mowing speed selector.

    The mower currently does not report mow_speed in the shadow, so the
    current value is intentionally unknown after startup. Once the user
    selects a speed, the last successfully sent option is kept locally for
    the lifetime of the entity.
    """

    _attr_has_entity_name = True
    _attr_name = "Mowing speed"
    _attr_icon = "mdi:speedometer"
    _attr_options = list(_SPEED_TO_RAW)

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_mowing_speed_setting"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )
        self._last_selected_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the last speed selected from Home Assistant."""
        return self._last_selected_option

    async def async_select_option(self, option: str) -> None:
        """Set mowing speed on the mower."""
        raw_value = _SPEED_TO_RAW.get(option)
        if raw_value is None:
            raise ValueError(f"Unsupported mowing speed: {option}")

        await self.coordinator.client.async_publish_service_command(
            cmd="param_set",
            data={"mow_speed": raw_value},
        )
        self._last_selected_option = option
        self.async_write_ha_state()

        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
