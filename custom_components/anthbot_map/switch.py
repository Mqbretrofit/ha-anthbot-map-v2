"""Switch platform for Anthbot Genie settings."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AnthbotGenieApiError
from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .zones import async_update_zone_settings, auto_zones, manual_zones


def _coerce_enabled_value(value: object) -> bool:
    """Map Anthbot integer/bool/string toggles to a Python bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"1", "true", "on", "enabled", "enable"}
    return False


def _is_custom_direction_enabled(value: object) -> bool:
    """Map raw enable_adaptive_head value to custom-direction toggle state."""
    return not _coerce_enabled_value(value)


@dataclass(frozen=True, kw_only=True)
class AnthbotSwitchDescription(SwitchEntityDescription):
    """Describes an Anthbot switch setting."""


SWITCHES: tuple[AnthbotSwitchDescription, ...] = (
    AnthbotSwitchDescription(
        key="custom_mowing_direction_enabled",
        translation_key="custom_mowing_direction_enabled",
        name="Custom mowing direction enabled",
    ),
    AnthbotSwitchDescription(
        key="visual_obstacle_detection_enabled",
        translation_key="visual_obstacle_detection_enabled",
        name="Visual obstacle detection",
    ),
    AnthbotSwitchDescription(
        key="rain_perception_enabled",
        translation_key="rain_perception_enabled",
        name="Rain perception",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot switch entities from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    entities: list[SwitchEntity] = [
        AnthbotSwitchEntity(coordinator, description)
        for coordinator in coordinators
        for description in SWITCHES
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
                entities.extend(
                    (
                        AnthbotZoneSwitchEntity(
                            coordinator, zone_kind, zone_id, "visual_obstacle"
                        ),
                        AnthbotZoneSwitchEntity(
                            coordinator, zone_kind, zone_id, "custom_direction"
                        ),
                        AnthbotZoneSwitchEntity(
                            coordinator, zone_kind, zone_id, "edge_cutting"
                        ),
                    )
                )
    async_add_entities(entities)


class AnthbotSwitchEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SwitchEntity
):
    """Anthbot switch entity."""

    entity_description: AnthbotSwitchDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotSwitchDescription,
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
    def is_on(self) -> bool:
        """Return current switch value."""
        state = self.coordinator.reported_state
        if self.entity_description.key == "rain_perception_enabled":
            return _coerce_enabled_value(state.get("rain_switch"))
        if self.entity_description.key == "visual_obstacle_detection_enabled":
            pobctl = state.get("pobctl")
            if isinstance(pobctl, dict):
                return _coerce_enabled_value(pobctl.get("switch"))
            device_config = state.get("device_config")
            if isinstance(device_config, dict):
                return _coerce_enabled_value(device_config.get("pobctl_switch"))
            return False

        param_set = state.get("param_set")
        if not isinstance(param_set, dict):
            return False
        return _is_custom_direction_enabled(param_set.get("enable_adaptive_head"))

    async def _async_set_custom_direction_enabled(self, enabled: bool) -> None:
        """Set custom mowing direction toggle."""
        param_set = self.coordinator.reported_state.get("param_set")
        mow_head = 0
        if isinstance(param_set, dict):
            value = param_set.get("mow_head")
            if isinstance(value, int):
                mow_head = value

        await self.coordinator.client.async_publish_service_command(
            cmd="param_set",
            data={
                "mow_head": mow_head,
                "enable_adaptive_head": 0 if enabled else 1,
            },
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def _async_set_visual_obstacle_detection_enabled(
        self, enabled: bool
    ) -> None:
        """Set camera-based obstacle detection."""
        state = self.coordinator.reported_state
        pobctl = state.get("pobctl")
        device_config = state.get("device_config")
        level = (
            pobctl.get("level")
            if isinstance(pobctl, dict)
            else (
                device_config.get("pobctl_level")
                if isinstance(device_config, dict)
                else 1
            )
        )
        if not isinstance(level, int) or level < 0 or level > 2:
            level = 1
        await self.coordinator.client.async_publish_service_command(
            cmd="perception_obstacle_ctl",
            data={"switch": 1 if enabled else 0, "level": level},
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    async def _async_set_rain_perception_enabled(self, enabled: bool) -> None:
        """Set rain perception toggle."""
        target_value = 1 if enabled else 0
        reported_continue_time = self.coordinator.reported_state.get("rain_continue_time")
        continue_time = (
            reported_continue_time
            if isinstance(reported_continue_time, int) and reported_continue_time > 0
            else 10800
        )

        await self.coordinator.client.async_publish_service_command(
            cmd="ctl_rainer",
            data={
                "switch": target_value,
                "continue_time": continue_time,
            },
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

        if self.is_on != enabled:
            raise AnthbotGenieApiError(
                "Rain perception command was accepted but the reported state did not change"
            )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn switch on."""
        if self.entity_description.key == "rain_perception_enabled":
            await self._async_set_rain_perception_enabled(True)
            return
        if self.entity_description.key == "visual_obstacle_detection_enabled":
            await self._async_set_visual_obstacle_detection_enabled(True)
            return
        await self._async_set_custom_direction_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn switch off."""
        if self.entity_description.key == "rain_perception_enabled":
            await self._async_set_rain_perception_enabled(False)
            return
        if self.entity_description.key == "visual_obstacle_detection_enabled":
            await self._async_set_visual_obstacle_detection_enabled(False)
            return
        await self._async_set_custom_direction_enabled(False)



class AnthbotZoneSwitchEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SwitchEntity
):
    """Editable app-compatible toggle for one manual or automatic zone."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        zone_kind: str,
        zone_id: int,
        setting: str,
    ) -> None:
        super().__init__(coordinator)
        self._zone_kind = zone_kind
        self._zone_id = zone_id
        self._setting = setting
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{zone_kind}_zone_"
            f"{zone_id}_{setting}_enabled"
        )
        zone = self._find_zone()
        zone_name = zone.get("name") if isinstance(zone, dict) else None
        kind_label = "Auto zone" if zone_kind == "auto" else "Zone"
        prefix = f"{kind_label} {zone_name or zone_id}"
        label = {
            "visual_obstacle": "Visual obstacle detection",
            "custom_direction": "Custom mowing direction",
            "edge_cutting": "Edge cutting",
        }[setting]
        self._attr_name = f"{prefix} {label}"
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
    def is_on(self) -> bool:
        zone = self._find_zone()
        if not isinstance(zone, dict):
            return False
        if self._setting == "visual_obstacle":
            return _coerce_enabled_value(
                zone.get("visual_ignore_obstacle_switch")
            )
        if self._setting == "edge_cutting":
            return _coerce_enabled_value(zone.get("mow_mode"))
        return _is_custom_direction_enabled(zone.get("enable_adaptive_head"))

    async def _async_set_enabled(self, enabled: bool) -> None:
        if self._setting == "visual_obstacle":
            updates = {"visual_ignore_obstacle_switch": 1 if enabled else 0}
        elif self._setting == "edge_cutting":
            updates = {"mow_mode": 1 if enabled else 0}
        else:
            updates = {"enable_adaptive_head": 0 if enabled else 1}
        await async_update_zone_settings(
            self.coordinator,
            zone_kind=self._zone_kind,
            zone_id=self._zone_id,
            updates=updates,
        )

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set_enabled(False)
