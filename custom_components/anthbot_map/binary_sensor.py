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
from .models.n8_control import is_n8_model
from .task_events import latest_task_cycle_signal, task_event_items


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


def _rain_hold_event(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the rain-return event while that task cycle is still held."""
    payload = data.get("_task_events")
    if latest_task_cycle_signal(payload) != "rain_return":
        return None
    for event in task_event_items(payload):
        try:
            code = int(event.get("code"))
        except (TypeError, ValueError):
            continue
        if code == 1036:
            return event
    return None


def _is_rain_hold(data: dict[str, Any]) -> bool:
    return _rain_hold_event(data) is not None


def _no_go_path_check(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("_no_go_path_check")
    return value if isinstance(value, dict) else {}


def _is_no_go_path_crossing(data: dict[str, Any]) -> bool:
    return _no_go_path_check(data).get("crossing_detected") is True


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
    AnthbotBinarySensorDescription(
        key="no_go_path_crossing",
        name="No-go path crossing",
        icon="mdi:map-marker-alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_is_no_go_path_crossing,
    ),
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
        value_fn=lambda data: _truthy(data.get("cellular_state")),
    ),
    AnthbotBinarySensorDescription(
        key="rain_hold",
        name="Rain hold",
        icon="mdi:weather-rainy",
        value_fn=_is_rain_hold,
    ),
    AnthbotBinarySensorDescription(
        key="log_upload_enabled",
        translation_key="log_upload_enabled",
        name="Log upload enabled",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("log_switch")),
    ),
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
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _truthy(data.get("user_unbind")),
    ),
)

N8_BINARY_SENSORS: tuple[AnthbotBinarySensorDescription, ...] = (
    AnthbotBinarySensorDescription(
        key="n8_dumping",
        name="Grass dumping",
        icon="mdi:delete-empty-outline",
        value_fn=lambda data: _truthy(data.get("_n8_dumping")),
    ),
    AnthbotBinarySensorDescription(
        key="n8_grass_bag_in_position",
        name="Grass bag in position",
        icon="mdi:delete-variant",
        value_fn=lambda data: _truthy(data.get("_n8_grass_bag_in_position")),
    ),
    AnthbotBinarySensorDescription(
        key="n8_grass_shield_in_position",
        name="Grass deflector in position",
        icon="mdi:shield-check-outline",
        value_fn=lambda data: _truthy(data.get("_n8_grass_shield_in_position")),
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
    entities: list[BinarySensorEntity] = [
        AnthbotBinarySensorEntity(coordinator, description)
        for coordinator in coordinators
        for description in BINARY_SENSORS
    ]
    for coordinator in coordinators:
        if is_n8_model(getattr(coordinator.device, "model", None)):
            entities.extend(
                AnthbotBinarySensorEntity(coordinator, description)
                for description in N8_BINARY_SENSORS
            )
    async_add_entities(entities)


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
        if self.entity_description.key == "rain_hold":
            event = _rain_hold_event(state)
            rain_continue_time = state.get("rain_continue_time")
            if isinstance(rain_continue_time, dict):
                rain_continue_time = rain_continue_time.get("value")
            return {
                "serial_number": self.coordinator.client.serial_number,
                "model": self.coordinator.device.model,
                "source": "task_event",
                "event_code": 1036 if event is not None else None,
                "rain_detected_at": event.get("create_time") if event else None,
                "event_message": event.get("event_message") if event else None,
                "rain_continue_time": rain_continue_time,
            }
        if self.entity_description.key == "no_go_path_crossing":
            check = _no_go_path_check(state)
            return {
                "serial_number": self.coordinator.client.serial_number,
                "model": self.coordinator.device.model,
                "source": check.get("source"),
                "path_id": check.get("path_id"),
                "checked_point_count": check.get("checked_point_count", 0),
                "checked_segment_count": check.get("checked_segment_count", 0),
                "no_go_zone_count": check.get("no_go_zone_count", 0),
                "points_inside": check.get("points_inside", 0),
                "boundary_crossings": check.get("boundary_crossings", 0),
                "traversals": check.get("traversals", 0),
                "zone_ids": check.get("zone_ids", []),
                "last_crossing": check.get("last_crossing"),
                "zones": check.get("zones", []),
            }
        cutting_height = (
            state.get("param_set", {}).get("cutter_height")
            if isinstance(state.get("param_set"), dict)
            else (
                state.get("mow_remote", {}).get("cutter_height")
                if isinstance(state.get("mow_remote"), dict)
                else None
            )
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
            "robot_status_raw": robot_sta_value,
        }
