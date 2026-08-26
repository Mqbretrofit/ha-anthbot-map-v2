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
from . import coordinator as coordinator_module
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .zones import async_update_zone_settings, auto_zones, manual_zones


# v2.4.1-test runtime hotfix: the mower can report "standby" while it is
# physically docked with charger power removed. Treat that as a docked state,
# and make the 55+1 minute guard resilient to short telemetry gaps.
coordinator_module._DOCKED_STATUS_VALUES.add("standby")


async def _battery_saver_shutdown_guard_loop_patched(self) -> None:
    """Pulse charger power after 55 minutes and retry transient telemetry gaps."""
    transient_statuses = {"", "unknown", "unavailable", "none"}
    try:
        while self._battery_saver_enabled:
            await asyncio.sleep(55 * 60)
            while self._battery_saver_enabled:
                config = self.battery_saver_config
                entity_id = config.get(coordinator_module.CONF_CHARGER_SWITCH)
                if not isinstance(entity_id, str) or not entity_id:
                    return
                switch_state = self.hass.states.get(entity_id)
                if switch_state is not None and switch_state.state == "on":
                    return

                status = self._robot_status(self.reported_state)
                battery = self._battery_percentage(self.reported_state)
                if battery is None or status in transient_statuses:
                    coordinator_module._LOGGER.debug(
                        "Battery saver guard telemetry unavailable for %s; retrying in 60 seconds",
                        self.client.serial_number,
                    )
                    await asyncio.sleep(60)
                    continue
                if status not in coordinator_module._DOCKED_STATUS_VALUES:
                    return

                if battery <= config[coordinator_module.CONF_MAINTENANCE_LEVEL]:
                    await self._async_set_charger(True)
                    return

                coordinator_module._LOGGER.info(
                    "Battery saver anti-shutdown pulse starting for %s",
                    self.client.serial_number,
                )
                await self._async_set_charger(True)
                await asyncio.sleep(60)

                status = self._robot_status(self.reported_state)
                battery = self._battery_percentage(self.reported_state)
                if not self._battery_saver_enabled:
                    return
                if status in coordinator_module._LIVE_STATUS_VALUES or status == "backtodock":
                    return
                if battery is None or status in transient_statuses:
                    coordinator_module._LOGGER.debug(
                        "Battery saver guard lost telemetry after pulse for %s; leaving charger power on",
                        self.client.serial_number,
                    )
                    return
                if status not in coordinator_module._DOCKED_STATUS_VALUES:
                    return
                if battery <= config[coordinator_module.CONF_MAINTENANCE_LEVEL]:
                    return

                await self._async_set_charger(False)
                coordinator_module._LOGGER.info(
                    "Battery saver anti-shutdown pulse completed for %s",
                    self.client.serial_number,
                )
                break
    except asyncio.CancelledError:
        raise
    finally:
        if asyncio.current_task() is self._battery_saver_shutdown_guard_task:
            self._battery_saver_shutdown_guard_task = None


AnthbotGenieDataUpdateCoordinator._async_shutdown_guard_loop = (
    _battery_saver_shutdown_guard_loop_patched
)


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
    AnthbotSwitchDescription(key="edge_following_return_enabled", name="Edge-following return"),
    AnthbotSwitchDescription(key="automatic_dock_mowing_enabled", name="Automatic dock-area mowing"),
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

    # If an old guard coroutine was started before the switch platform loaded,
    # restart it so the patched implementation is used immediately after HA
    # startup instead of waiting for the next charger-off transition.
    for coordinator in coordinators:
        guard = coordinator._battery_saver_shutdown_guard_task
        if guard is not None and not guard.done():
            guard.cancel()
            coordinator._battery_saver_shutdown_guard_task = None
        config = coordinator.battery_saver_config
        entity_id = config.get(coordinator_module.CONF_CHARGER_SWITCH)
        switch_state = hass.states.get(entity_id) if isinstance(entity_id, str) else None
        if (
            coordinator.battery_saver_enabled
            and isinstance(entity_id, str)
            and entity_id
            and (switch_state is None or switch_state.state != "on")
        ):
            coordinator._ensure_shutdown_guard()

    entities: list[SwitchEntity] = [
        AnthbotSwitchEntity(coordinator, description)
        for coordinator in coordinators
        for description in SWITCHES
    ]
    entities.extend(AnthbotBatterySaverSwitchEntity(coordinator) for coordinator in coordinators)
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


class AnthbotBatterySaverSwitchEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SwitchEntity
):
    """Persistent local guard for the optional battery-saver automation."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery_saver_mode"
    _attr_name = "Battery saver mode"
    _attr_icon = "mdi:battery-heart-variant"

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_battery_saver_mode"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def is_on(self) -> bool:
        """Return the persisted local mode state."""
        return self.coordinator.battery_saver_enabled

    @property
    def available(self) -> bool:
        """Keep the local guard available even if the cloud is temporarily offline."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose the per-mower charger and thresholds used by the mode."""
        config = self.coordinator.battery_saver_config
        return {
            **config,
            "configured": bool(config.get("charger_switch")),
            "phase": self.coordinator.battery_saver_phase,
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Arm battery-saving behavior."""
        await self.coordinator.async_set_battery_saver_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disarm battery-saving behavior."""
        await self.coordinator.async_set_battery_saver_enabled(False)


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
        if self.entity_description.key == "edge_following_return_enabled":
            return _coerce_enabled_value(param_set.get("rid_switch"))
        if self.entity_description.key == "automatic_dock_mowing_enabled":
            return _coerce_enabled_value(param_set.get("nest_switch"))
        return _is_custom_direction_enabled(param_set.get("enable_adaptive_head"))

    async def _async_set_param_toggle(self, field: str, enabled: bool) -> None:
        await self.coordinator.client.async_publish_service_command(
            cmd="param_set", data={field: 1 if enabled else 0}
        )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

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
        if self.entity_description.key == "edge_following_return_enabled":
            await self._async_set_param_toggle("rid_switch", True)
            return
        if self.entity_description.key == "automatic_dock_mowing_enabled":
            await self._async_set_param_toggle("nest_switch", True)
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
        if self.entity_description.key == "edge_following_return_enabled":
            await self._async_set_param_toggle("rid_switch", False)
            return
        if self.entity_description.key == "automatic_dock_mowing_enabled":
            await self._async_set_param_toggle("nest_switch", False)
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
