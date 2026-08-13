"""Number platform for Anthbot Genie settings."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .zones import async_update_zone_settings, auto_zones, manual_zones


@dataclass(frozen=True, kw_only=True)
class AnthbotNumberDescription(NumberEntityDescription):
    """Describes an Anthbot number setting."""

    getter: Callable


NUMBERS: tuple[AnthbotNumberDescription, ...] = (
    AnthbotNumberDescription(
        key="mow_height_setting",
        translation_key="mow_height_setting",
        name="Mow height",
        native_min_value=30,
        native_max_value=70,
        native_step=5,
        native_unit_of_measurement="mm",
        mode=NumberMode.SLIDER,
        getter=lambda data: (
            data.get("param_set", {}).get("cutter_height")
            if isinstance(data.get("param_set"), dict)
            else (
                data.get("mow_remote", {}).get("cutter_height")
                if isinstance(data.get("mow_remote"), dict)
                else None
            )
        ),
    ),
    AnthbotNumberDescription(
        key="mow_count_setting",
        translation_key="mow_count_setting",
        name="Mowing passes",
        native_min_value=1,
        native_max_value=3,
        native_step=1,
        mode=NumberMode.SLIDER,
        getter=lambda data: (
            data.get("param_set", {}).get("mow_count")
            if isinstance(data.get("param_set"), dict)
            else None
        ),
    ),
    AnthbotNumberDescription(
        key="visual_obstacle_level_setting",
        translation_key="visual_obstacle_level_setting",
        name="Visual obstacle sensitivity",
        native_min_value=0,
        native_max_value=2,
        native_step=1,
        mode=NumberMode.SLIDER,
        getter=lambda data: (
            data.get("pobctl", {}).get("level")
            if isinstance(data.get("pobctl"), dict)
            else (
                data.get("device_config", {}).get("pobctl_level")
                if isinstance(data.get("device_config"), dict)
                else None
            )
        ),
    ),
    AnthbotNumberDescription(
        key="voice_volume_setting",
        translation_key="voice_volume_setting",
        name="Voice volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        getter=lambda data: data.get("volume"),
    ),
    AnthbotNumberDescription(
        key="custom_mowing_direction_setting",
        translation_key="custom_mowing_direction_setting",
        name="Custom mowing direction",
        native_min_value=0,
        native_max_value=180,
        native_step=1,
        native_unit_of_measurement="deg",
        mode=NumberMode.SLIDER,
        getter=lambda data: (
            data.get("param_set", {}).get("mow_head")
            if isinstance(data.get("param_set"), dict)
            else None
        ),
    ),
    AnthbotNumberDescription(
        key="rain_continue_time_setting",
        translation_key="rain_continue_time_setting",
        name="Rain continue time",
        native_min_value=0,
        native_max_value=8,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.HOURS,
        mode=NumberMode.SLIDER,
        getter=lambda data: (
            data.get("rain_continue_time") / 3600
            if isinstance(data.get("rain_continue_time"), (int, float))
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot number entities from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    entities: list[NumberEntity] = [
        AnthbotNumberEntity(coordinator, description)
        for coordinator in coordinators
        for description in NUMBERS
    ]
    for coordinator in coordinators:
        for zone_kind, zones in (
            ("manual", manual_zones(coordinator.reported_state)),
            ("auto", auto_zones(coordinator.reported_state)),
        ):
            for zone in zones:
                zone_id = zone.get("id")
                if not isinstance(zone_id, int):
                    continue
                for setting in (
                    "mow_count",
                    "cutter_height",
                    "obstacle_avoid_level",
                    "mow_head",
                ):
                    entities.append(
                        AnthbotZoneNumberEntity(
                            coordinator, zone_kind, zone_id, setting
                        )
                    )
    async_add_entities(entities)


class AnthbotNumberEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], NumberEntity
):
    """Anthbot number entity."""

    entity_description: AnthbotNumberDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def native_value(self) -> float | None:
        """Return current value."""
        value = self.entity_description.getter(self.coordinator.reported_state)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set value on mower."""
        int_value = int(round(value))
        key = self.entity_description.key
        if key == "mow_height_setting":
            if int_value < 30 or int_value > 70 or int_value % 5 != 0:
                raise ValueError("Mow height must be 30..70 in 5 mm steps")
            await self.coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={"cutter_height": int_value, "rid_switch": 0},
            )
        elif key == "mow_count_setting":
            if int_value < 1 or int_value > 3:
                raise ValueError("Mowing passes must be 1..3")
            await self.coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={"mow_count": int_value},
            )
        elif key == "visual_obstacle_level_setting":
            if int_value < 0 or int_value > 2:
                raise ValueError("Visual obstacle sensitivity must be 0..2")
            state = self.coordinator.reported_state
            pobctl = state.get("pobctl")
            device_config = state.get("device_config")
            switch_value = (
                pobctl.get("switch")
                if isinstance(pobctl, dict)
                else (
                    device_config.get("pobctl_switch")
                    if isinstance(device_config, dict)
                    else 1
                )
            )
            await self.coordinator.client.async_publish_service_command(
                cmd="perception_obstacle_ctl",
                data={
                    "switch": 1 if switch_value in (1, "1", True, "true", "on") else 0,
                    "level": int_value,
                },
            )
        elif key == "voice_volume_setting":
            if int_value < 0 or int_value > 100:
                raise ValueError("Voice volume must be 0..100")
            await self.coordinator.client.async_publish_service_command(
                cmd="volume_ctl",
                data={"volume": int_value},
            )
        elif key == "custom_mowing_direction_setting":
            if int_value < 0 or int_value > 180:
                raise ValueError("Custom mowing direction must be 0..180")
            await self.coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={
                    "mow_head": int_value,
                    "enable_adaptive_head": 0,
                },
            )
        elif key == "rain_continue_time_setting":
            if int_value < 0 or int_value > 8:
                raise ValueError("Rain continue time must be 0..8 hours")
            rain_switch = self.coordinator.reported_state.get("rain_switch")
            switch_value = 1 if rain_switch in (1, "1", True, "true", "on") else 0
            await self.coordinator.client.async_publish_service_command(
                cmd="ctl_rainer",
                data={
                    "switch": switch_value,
                    "continue_time": int_value * 3600,
                },
            )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()


_ZONE_NUMBER_SETTINGS: dict[str, tuple[str, float, float, float, str | None]] = {
    "mow_count": ("Mowing passes", 1, 3, 1, None),
    "cutter_height": ("Cutting height", 30, 70, 5, "mm"),
    "obstacle_avoid_level": ("Obstacle sensitivity", 0, 2, 1, None),
    "mow_head": ("Mowing direction", 0, 180, 1, "deg"),
}


class AnthbotZoneNumberEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], NumberEntity
):
    """Editable app-compatible setting for one manual or automatic zone."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        zone_kind: str,
        zone_id: int,
        setting: str,
    ) -> None:
        super().__init__(coordinator)
        label, minimum, maximum, step, unit = _ZONE_NUMBER_SETTINGS[setting]
        self._zone_kind = zone_kind
        self._zone_id = zone_id
        self._setting = setting
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{zone_kind}_zone_"
            f"{zone_id}_{setting}_setting"
        )
        zone = self._find_zone()
        zone_name = zone.get("name") if isinstance(zone, dict) else None
        kind_label = "Auto zone" if zone_kind == "auto" else "Zone"
        prefix = f"{kind_label} {zone_name or zone_id}"
        self._attr_name = f"{prefix} {label}"
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    def _find_zone(self) -> dict | None:
        zones = (
            manual_zones(self.coordinator.reported_state)
            if self._zone_kind == "manual"
            else auto_zones(self.coordinator.reported_state)
        )
        return next((zone for zone in zones if zone.get("id") == self._zone_id), None)

    @property
    def native_value(self) -> float | None:
        zone = self._find_zone()
        if not isinstance(zone, dict):
            return None
        value = zone.get(self._setting)
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(round(value))
        _, minimum, maximum, step, _ = _ZONE_NUMBER_SETTINGS[self._setting]
        if int_value < minimum or int_value > maximum:
            raise ValueError(f"{self._setting} must be {minimum}..{maximum}")
        if step > 1 and int_value % int(step) != 0:
            raise ValueError(f"{self._setting} must use {step:g} steps")
        updates: dict[str, int] = {self._setting: int_value}
        if self._setting == "mow_head":
            updates["enable_adaptive_head"] = 0
        await async_update_zone_settings(
            self.coordinator,
            zone_kind=self._zone_kind,
            zone_id=self._zone_id,
            updates=updates,
        )
