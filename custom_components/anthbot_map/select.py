"""Select platform for Anthbot Genie raw mowing mode diagnostics."""

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

_MODE_TO_RAW: dict[str, int] = {
    "Mode 0": 0,
    "Mode 1": 1,
}
_RAW_TO_MODE = {value: key for key, value in _MODE_TO_RAW.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot select entities from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotMowingModeSelect(coordinator) for coordinator in coordinators
    )


class AnthbotMowingModeSelect(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SelectEntity
):
    """Raw Genie mowing mode selector for protocol testing."""

    _attr_has_entity_name = True
    _attr_name = "Mowing mode raw"
    _attr_icon = "mdi:format-list-bulleted"
    _attr_options = list(_MODE_TO_RAW)

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_mowing_mode_raw_setting"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def current_option(self) -> str | None:
        """Return current raw mow_mode from the reported state."""
        param_set = self.coordinator.reported_state.get("param_set")
        if not isinstance(param_set, dict):
            return None
        value = param_set.get("mow_mode")
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return None
        if isinstance(value, (int, float)):
            return _RAW_TO_MODE.get(int(value))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        """Expose the exact raw reported value for diagnosis."""
        param_set = self.coordinator.reported_state.get("param_set")
        value = param_set.get("mow_mode") if isinstance(param_set, dict) else None
        return {"raw_mow_mode": value}

    async def async_select_option(self, option: str) -> None:
        """Set the raw Genie mow_mode value."""
        raw_value = _MODE_TO_RAW.get(option)
        if raw_value is None:
            raise ValueError(f"Unsupported mowing mode: {option}")

        await self.coordinator.client.async_publish_service_command(
            cmd="param_set",
            data={"mow_mode": raw_value},
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
