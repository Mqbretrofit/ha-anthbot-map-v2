"""Binary sensor platform for Anthbot Genie."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator


def _safe_get(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _truthy(value: Any) -> bool:
    """Generic 'is this ON?' coercion for the mower's int/bool/string flags."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "enabled"}
    return False


def _nonzero(value: Any) -> bool:
    """For error-style fields where "present" means "not zero"."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value not in ("", "0")
    return False


def _is_connected(data: dict[str, Any]) -> bool:
    online = data.get("online")
    if isinstance(online, bool):
        return online
    if isinstance(online, str):
        return online == "1"
    if isinstance(online, int):
        return online == 1
    return False


def _is_charging(data: dict[str, Any]) -> bool:
    robot_sta = data.get("robot_sta")
    if not isinstance(robot_sta, dict):
        return False
    value = robot_sta.get("value")
    if not isinstance(value, str):
        return False
    return value.lower() in {"charge", "charging", "charge_start"}


def _is_custom_mowing_direction_enabled(data: dict[str, Any]) -> bool:
    param_set = data.get("param_set")
    if not isinstance(param_set, dict):
        return False
    value = param_set.get("enable_adaptive_head")
    adaptive_enabled = False
    if isinstance(value, bool):
        adaptive_enabled = value
    elif isinstance(value, int):
        adaptive_enabled = value == 1
    elif isinstance(value, str):
        adaptive_enabled = value == "1"
    return not adaptive_enabled


@dataclass(frozen=True, kw_only=True)
class AnthbotBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an Anthbot binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[AnthbotBinarySensorDescription, ...] = (
    AnthbotBinarySensorDescription(
        key="connection",
        translation_key="connection",
        name="Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=_is_connected,
    ),
    AnthbotBinarySensorDescription(
        key="charging",
        translation_key="charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_is_charging,
    ),
    # --- Error presence -------------------------------------------------
    AnthbotBinarySensorDescription(
        key="error_active",
        translation_key="error_active",
        name="Error active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: _nonzero(data.get("err_code")),
    ),
    AnthbotBinarySensorDescription(
        key="camera_error",
        translation_key="camera_error",
        name="Camera error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _nonzero(_safe_get(data, "camera_error_sta", "value")),
    ),
    # --- Connectivity flags ---------------------------------------------
    AnthbotBinarySensorDescription(
        key="wifi_connected",
        translation_key="wifi_connected",
        name="WiFi connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("wifi_state")),
    ),
    AnthbotBinarySensorDescription(
        key="cellular_connected",
        translation_key="cellular_connected",
        name="Cellular connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("4g_state")),
    ),
    AnthbotBinarySensorDescription(
        key="cellular_heartbeat",
        translation_key="cellular_heartbeat",
        name="Cellular heartbeat",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("heart_4g")),
    ),
    AnthbotBinarySensorDescription(
        key="bluetooth_active",
        translation_key="bluetooth_active",
        name="Bluetooth active",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("bt_state")),
    ),
    AnthbotBinarySensorDescription(
        key="sim_present",
        translation_key="sim_present",
        name="SIM inserted",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(_safe_get(data, "sim_status", "status")),
    ),
    # --- Map / mowing lifecycle -----------------------------------------
    AnthbotBinarySensorDescription(
        key="map_available",
        translation_key="map_available",
        name="Map available",
        value_fn=lambda data: _nonzero(_safe_get(data, "has_map", "value")),
    ),
    AnthbotBinarySensorDescription(
        key="rtk_moving",
        translation_key="rtk_moving",
        name="RTK moving",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _nonzero(_safe_get(data, "rtk_move_sta", "value")),
    ),
    AnthbotBinarySensorDescription(
        key="accelerometer_active",
        translation_key="accelerometer_active",
        name="Accelerometer active",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(_safe_get(data, "acc_sta", "value")),
    ),
    AnthbotBinarySensorDescription(
        key="mowing_border",
        translation_key="mowing_border",
        name="Mowing border",
        value_fn=lambda data: _nonzero(_safe_get(data, "mow_border", "value")),
    ),
    AnthbotBinarySensorDescription(
        key="mowing_nest",
        translation_key="mowing_nest",
        name="Mowing nest",
        value_fn=lambda data: _nonzero(_safe_get(data, "mow_nest", "value")),
    ),
    AnthbotBinarySensorDescription(
        key="full_yard_mowing",
        translation_key="full_yard_mowing",
        name="Full-yard mowing enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("mow_full")),
    ),
    # --- State flags mirroring switches (read-only copy) ----------------
    AnthbotBinarySensorDescription(
        key="anti_loss_state",
        translation_key="anti_loss_state",
        name="Anti-loss state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("anti_loss_switch")),
    ),
    AnthbotBinarySensorDescription(
        key="camera_state",
        translation_key="camera_state",
        name="Camera state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("camera_switch")),
    ),
    AnthbotBinarySensorDescription(
        key="edge_cut_state",
        translation_key="edge_cut_state",
        name="Edge-cut state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("edge_switch")),
    ),
    AnthbotBinarySensorDescription(
        key="indoor_mode_state",
        translation_key="indoor_mode_state",
        name="Indoor mode state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("indoor_switch")),
    ),
    AnthbotBinarySensorDescription(
        key="auto_upgrade_state",
        translation_key="auto_upgrade_state",
        name="Auto upgrade state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("auto_upgrade")),
    ),
    AnthbotBinarySensorDescription(
        key="obstacle_avoidance_state",
        translation_key="obstacle_avoidance_state",
        name="Obstacle avoidance state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(_safe_get(data, "pobctl", "switch")),
    ),
    AnthbotBinarySensorDescription(
        key="drc_enabled",
        translation_key="drc_enabled",
        name="DRC enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("drc_switch")),
    ),
    AnthbotBinarySensorDescription(
        key="log_upload_enabled",
        translation_key="log_upload_enabled",
        name="Log upload enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("log_switch")),
    ),
    # --- Admin flags ----------------------------------------------------
    AnthbotBinarySensorDescription(
        key="factory_reset_pending",
        translation_key="factory_reset_pending",
        name="Factory reset pending",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("factory_reset")),
    ),
    AnthbotBinarySensorDescription(
        key="unbind_pending",
        translation_key="unbind_pending",
        name="User unbind pending",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("user_unbind")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot binary sensors from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(
        AnthbotBinarySensorEntity(coordinator, description)
        for coordinator in coordinators
        for description in BINARY_SENSORS
    )


class AnthbotBinarySensorEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], BinarySensorEntity
):
    """Anthbot binary sensor entity."""

    entity_description: AnthbotBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotBinarySensorDescription,
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
        """Return current binary sensor value."""
        return self.entity_description.value_fn(self.coordinator.reported_state)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        state = self.coordinator.reported_state
        cutting_height = (
            state.get("param_set", {}).get("cutter_height")
            if isinstance(state.get("param_set"), dict)
            else (
                state.get("mow_remote", {}).get("cutter_height")
                if isinstance(state.get("mow_remote"), dict)
                else None
            )
        )
        service_reported = (
            state.get("_service_reported")
            if isinstance(state.get("_service_reported"), dict)
            else None
        )
        mowing_time = (
            state.get("mowing_time_new", {}).get("value")
            if isinstance(state.get("mowing_time_new"), dict)
            else None
        )
        mowing_area = (
            state.get("mowing_area_new", {}).get("value")
            if isinstance(state.get("mowing_area_new"), dict)
            else None
        )
        custom_mowing_direction = (
            state.get("param_set", {}).get("mow_head")
            if isinstance(state.get("param_set"), dict)
            else None
        )
        custom_mowing_direction_enabled = (
            _is_custom_mowing_direction_enabled(state)
            if isinstance(state.get("param_set"), dict)
            else False
        )
        voice_volume = state.get("volume")
        voice_status = (
            state.get("voice_status")
            if isinstance(state.get("voice_status"), dict)
            else None
        )
        robot_sta = state.get("robot_sta")
        robot_sta_value = (
            robot_sta.get("value")
            if isinstance(robot_sta, dict)
            else robot_sta
        )
        return {
            "serial_number": self.coordinator.client.serial_number,
            "cutting_height": cutting_height,
            "mowing_time": mowing_time,
            "mowing_area": mowing_area,
            "custom_mowing_direction": custom_mowing_direction,
            "custom_mowing_direction_enabled": custom_mowing_direction_enabled,
            "voice_volume": voice_volume,
            "voice_status": voice_status,
            "robot_sta": robot_sta_value,
            "last_service_command": (
                service_reported.get("cmd") if service_reported else None
            ),
            "last_service_command_generation": (
                service_reported.get("generation") if service_reported else None
            ),
        }
