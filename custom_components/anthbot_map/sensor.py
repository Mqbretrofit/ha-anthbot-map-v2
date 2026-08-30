"""Sensor platform for Anthbot Genie."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfArea,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ERROR_CODE_DESCRIPTIONS,
    RTK_BASE_STATE_OPTIONS,
    RTK_STATE_OPTIONS,
)
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .task_events import (
    latest_task_event,
    task_event_code,
    task_event_datetime,
    task_event_items,
    task_event_value,
)
from .zones import active_manual_zone_ids, auto_zones, manual_zones, ridable_areas


def _safe_get(data: dict[str, Any], *path: str) -> Any:
    """Walk a nested dict path, returning None if any hop is missing."""
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return None
    return None


def _battery_level(data: dict[str, Any]) -> int | None:
    """Return a validated battery percentage for all known payload formats."""
    raw_value = data.get("elec")
    seen_wrappers: set[int] = set()
    while isinstance(raw_value, dict):
        wrapper_id = id(raw_value)
        if wrapper_id in seen_wrappers:
            return None
        seen_wrappers.add(wrapper_id)
        raw_value = raw_value.get("value")

    value = _as_int(raw_value)
    if value is None or not 0 <= value <= 100:
        return None
    return value



def _as_datetime(value: Any) -> datetime | None:
    """Parse Unix-epoch integers and 'YYYYMMDDHHMMSS' strings to UTC datetimes."""
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and len(value) == 14 and value.isdigit():
        try:
            anthbot_timezone = timezone(timedelta(hours=8))
            return (
                datetime.strptime(value, "%Y%m%d%H%M%S")
                .replace(tzinfo=anthbot_timezone)
                .astimezone(timezone.utc)
            )
        except ValueError:
            return None
    return None


def _is_custom_mowing_direction_enabled(data: dict[str, Any]) -> bool:
    """Map raw enable_adaptive_head value to custom-direction state."""
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


_ROBOT_STATUS_BY_CODE: tuple[str, ...] = (
    "idle",
    "pause",
    "charge",
    "sleep",
    "ota",
    "position",
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "mapping",
    "backtodock",
    "resume_point",
    "shutdown",
    "remotectrl",
    "factory",
    "sleep",
    "camera_cleaning",
    "gototarget",
    "bordermowing",
    "regionmowing",
    "nestmowing",
)

MOWER_STATUS_OPTIONS: list[str] = [
    "standby",
    "paused",
    "charging",
    "mowing",
    "returning_to_dock",
    "mapping",
    "positioning",
    "resuming",
    "sleeping",
    "ota_updating",
    "remote_control",
    "factory_mode",
    "camera_cleaning",
    "going_to_target",
    "shutdown",
    "unknown",
]


def _raw_robot_status(data: dict[str, Any]) -> str | None:
    """Return raw robot status from shadow payload."""
    robot_sta = data.get("robot_sta")
    if not isinstance(robot_sta, dict):
        return None
    value = robot_sta.get("value")
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, int):
        if 0 <= value < len(_ROBOT_STATUS_BY_CODE):
            return _ROBOT_STATUS_BY_CODE[value]
        return str(value)
    return None


def _general_mower_status(data: dict[str, Any]) -> str:
    """Map raw robot status to a human-readable general status."""
    raw = _raw_robot_status(data)
    if raw is None:
        return "unknown"

    if raw in {
        "globalmowing",
        "zonemowing",
        "pointmowing",
        "bordermowing",
        "regionmowing",
        "nestmowing",
    }:
        return "mowing"
    if raw in {"charge", "charging", "charge_start"}:
        return "charging"
    if raw == "backtodock":
        return "returning_to_dock"
    if raw == "idle":
        return "standby"
    if raw == "pause":
        return "paused"
    if raw == "mapping":
        return "mapping"
    if raw == "position":
        return "positioning"
    if raw == "resume_point":
        return "resuming"
    if raw == "sleep":
        return "sleeping"
    if raw == "ota":
        return "ota_updating"
    if raw == "remotectrl":
        return "remote_control"
    if raw == "factory":
        return "factory_mode"
    if raw == "camera_cleaning":
        return "camera_cleaning"
    if raw == "gototarget":
        return "going_to_target"
    if raw == "shutdown":
        return "shutdown"
    return "unknown"


@dataclass(frozen=True, kw_only=True)
class AnthbotSensorDescription(SensorEntityDescription):
    """Describes an Anthbot sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]


def _error_description(data: dict[str, Any]) -> str | None:
    code = _as_int(data.get("err_code"))
    if code is None:
        return None
    return ERROR_CODE_DESCRIPTIONS.get(code, f"Unknown error ({code})")


def _rtk_state_label(data: dict[str, Any]) -> str | None:
    code = _as_int(data.get("rtk_state"))
    if code is None:
        return None
    return RTK_STATE_OPTIONS.get(code, "unknown")


def _rtk_base_state_label(data: dict[str, Any]) -> str | None:
    code = _as_int(_safe_get(data, "ctl_rtk_base", "rtk_base_state"))
    if code is None:
        return None
    return RTK_BASE_STATE_OPTIONS.get(code, "unknown")


SENSORS: tuple[AnthbotSensorDescription, ...] = (
    # --- Primary mower status --------------------------------------------
    AnthbotSensorDescription(
        key="mower_status",
        translation_key="mower_status",
        name="Mower status",
        device_class=SensorDeviceClass.ENUM,
        options=MOWER_STATUS_OPTIONS,
        value_fn=_general_mower_status,
    ),
    AnthbotSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_battery_level,
    ),
    AnthbotSensorDescription(
        key="voice_volume",
        translation_key="voice_volume",
        name="Voice volume",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("volume"),
    ),
    AnthbotSensorDescription(
        key="cutting_height",
        translation_key="cutting_height",
        name="Cutting height",
        native_unit_of_measurement="mm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            _safe_get(data, "param_set", "cutter_height")
            or _safe_get(data, "mow_remote", "cutter_height")
        ),
    ),
    AnthbotSensorDescription(
        key="mowing_time",
        translation_key="mowing_time",
        name="Mowing time (session)",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "mowing_time_new", "value"),
    ),
    AnthbotSensorDescription(
        key="mowing_area",
        translation_key="mowing_area",
        name="Mowing area (session)",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "mowing_area_new", "value"),
    ),

    AnthbotSensorDescription(
        key="custom_mowing_direction",
        translation_key="custom_mowing_direction",
        name="Custom mowing direction",
        native_unit_of_measurement="deg",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "param_set", "mow_head"),
    ),
    AnthbotSensorDescription(
        key="custom_mowing_direction_enabled",
        translation_key="custom_mowing_direction_enabled",
        name="Custom mowing direction enabled",
        device_class=SensorDeviceClass.ENUM,
        options=["enabled", "disabled"],
        value_fn=lambda data: (
            "enabled" if _is_custom_mowing_direction_enabled(data) else "disabled"
        ),
    ),
    AnthbotSensorDescription(
        key="zones",
        translation_key="zones",
        name="Zones",
        value_fn=lambda data: len(manual_zones(data)),
    ),
    AnthbotSensorDescription(
        key="auto_zones",
        translation_key="auto_zones",
        name="Auto zones",
        value_fn=lambda data: len(auto_zones(data)),
    ),
    # --- Map / area ------------------------------------------------------
    AnthbotSensorDescription(
        key="total_map_area",
        translation_key="total_map_area",
        name="Total mapped area",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        device_class=SensorDeviceClass.AREA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("map_area"),
    ),
    AnthbotSensorDescription(
        key="map_status",
        translation_key="map_status",
        name="Map status",
        value_fn=lambda data: _safe_get(data, "map_sta", "value"),
    ),
    # --- Errors / events -------------------------------------------------
    AnthbotSensorDescription(
        key="error_code",
        translation_key="error_code",
        name="Error code",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _as_int(data.get("err_code")),
    ),
    AnthbotSensorDescription(
        key="error_description",
        translation_key="error_description",
        name="Error description",
        value_fn=_error_description,
    ),
    AnthbotSensorDescription(
        key="event_code",
        translation_key="event_code",
        name="Last event code",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _as_int(data.get("event_code")),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_code",
        name="Cloud task event code",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: task_event_code(data.get("_task_events")),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_text",
        name="Cloud task event text",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: task_event_value(
            data.get("_task_events"), "event_message"
        ),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_type",
        name="Cloud task event type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: task_event_value(data.get("_task_events"), "code_type"),
    ),
    AnthbotSensorDescription(
        key="cloud_task_event_time",
        name="Cloud task event time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: task_event_datetime(data.get("_task_events")),
    ),
    # --- Positioning / RTK ----------------------------------------------
    AnthbotSensorDescription(
        key="rtk_state",
        translation_key="rtk_state",
        name="RTK fix state",
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(list(RTK_STATE_OPTIONS.values()) + ["unknown"])),
        value_fn=_rtk_state_label,
    ),
    AnthbotSensorDescription(
        key="rtk_base_state",
        translation_key="rtk_base_state",
        name="RTK base station state",
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(list(RTK_BASE_STATE_OPTIONS.values()) + ["unknown"])),
        value_fn=_rtk_base_state_label,
    ),
    AnthbotSensorDescription(
        key="gps_latitude",
        translation_key="gps_latitude",
        name="GPS latitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "anti_loss_pose", "posegps", "lat"),
    ),
    AnthbotSensorDescription(
        key="gps_longitude",
        translation_key="gps_longitude",
        name="GPS longitude",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "anti_loss_pose", "posegps", "lon"),
    ),
    # --- Maintenance percentages ----------------------------------------
    AnthbotSensorDescription(
        key="cutting_component_life",
        translation_key="cutting_component_life",
        name="Cutting components life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "robot_maintenance", "ccp_pecent"),
    ),
    AnthbotSensorDescription(
        key="cutting_line_life",
        translation_key="cutting_line_life",
        name="Cutting line life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "robot_maintenance", "cl_pecent"),
    ),
    AnthbotSensorDescription(
        key="recharge_contact_life",
        translation_key="recharge_contact_life",
        name="Recharge contact life",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "robot_maintenance", "rc_pecent"),
    ),
    # --- Firmware / versions --------------------------------------------
    AnthbotSensorDescription(
        key="firmware_version",
        translation_key="firmware_version",
        name="Firmware version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "system_version"),
    ),
    AnthbotSensorDescription(
        key="main_board_version",
        translation_key="main_board_version",
        name="Main board version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "main_board"),
    ),
    AnthbotSensorDescription(
        key="extension_board_version",
        translation_key="extension_board_version",
        name="Extension board version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "exten_board"),
    ),
    AnthbotSensorDescription(
        key="rtk_base_firmware",
        translation_key="rtk_base_firmware",
        name="RTK base firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "fw_version", "rtk_base"),
    ),
    AnthbotSensorDescription(
        key="protocol_version",
        translation_key="protocol_version",
        name="Protocol version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("protocol_version"),
    ),
    AnthbotSensorDescription(
        key="minimum_app_version",
        translation_key="minimum_app_version",
        name="Minimum app version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("min_app_version"),
    ),
    # --- OTA -------------------------------------------------------------
    AnthbotSensorDescription(
        key="ota_progress",
        translation_key="ota_progress",
        name="OTA progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "ota_status", "ota_progress"),
    ),
    AnthbotSensorDescription(
        key="ota_state",
        translation_key="ota_state",
        name="OTA state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "ota_status", "ota_state"),
    ),
    AnthbotSensorDescription(
        key="ota_time_estimate",
        translation_key="ota_time_estimate",
        name="OTA time estimate",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "ota_status", "ota_time_estimate"),
    ),
    # --- Network diagnostics --------------------------------------------
    AnthbotSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        name="WiFi SSID",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("sta_ssid"),
    ),
    AnthbotSensorDescription(
        key="ip_address",
        translation_key="ip_address",
        name="IP address",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("sta_ip_addr"),
    ),
    AnthbotSensorDescription(
        key="sim_ccid",
        translation_key="sim_ccid",
        name="SIM CCID",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("4g_ccid"),
    ),
    # --- Misc diagnostics -----------------------------------------------
    AnthbotSensorDescription(
        key="pin_code",
        translation_key="pin_code",
        name="Device PIN",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_int(data.get("pin_code")),
    ),
    AnthbotSensorDescription(
        key="voice_language",
        translation_key="voice_language",
        name="Voice language",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _safe_get(data, "voice_status", "name")
            or _safe_get(data, "music_cfg", "music_language")
        ),
    ),
    AnthbotSensorDescription(
        key="obstacle_avoidance_level",
        translation_key="obstacle_avoidance_level",
        name="Obstacle avoidance level",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _safe_get(data, "pobctl", "level"),
    ),
    AnthbotSensorDescription(
        key="mow_count",
        translation_key="mow_count",
        name="Pass count setting",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "param_set", "mow_count"),
    ),
    AnthbotSensorDescription(
        key="anti_loss_radius",
        translation_key="anti_loss_radius",
        name="Anti-loss radius",
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_int(data.get("anti_loss_radius")),
    ),
    # --- v1.0.0: Absolute pose ------------------------------------------
    # `pose` reports x/y in cm and yaw in degrees, separate from the
    # (lat,lon) GPS reading. Useful for plotting on a 2D map.
    AnthbotSensorDescription(
        key="pose_x",
        translation_key="pose_x",
        name="Position X",
        native_unit_of_measurement="cm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "pose", "x"),
    ),
    AnthbotSensorDescription(
        key="pose_y",
        translation_key="pose_y",
        name="Position Y",
        native_unit_of_measurement="cm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "pose", "y"),
    ),
    AnthbotSensorDescription(
        key="pose_yaw",
        translation_key="pose_yaw",
        name="Heading",
        native_unit_of_measurement="°",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _safe_get(data, "pose", "yaw"),
    ),
    # --- v1.0.0: Active mowing zone -------------------------------------
    AnthbotSensorDescription(
        key="active_zone_id",
        translation_key="active_zone_id",
        name="Active zone",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _safe_get(data, "active_area", "id")[0]
            if isinstance(_safe_get(data, "active_area", "id"), list)
            and _safe_get(data, "active_area", "id")
            else None
        ),
    ),
    # --- v1.0.0: Forbid (no-go) zones count ------------------------------
    AnthbotSensorDescription(
        key="forbid_zones_count",
        translation_key="forbid_zones_count",
        name="No-go zones",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            len(_safe_get(data, "_area_definition", "forbid_areas") or [])
        ),
    ),
    # --- Timestamps ------------------------------------------------------
    AnthbotSensorDescription(
        key="shadow_updated",
        translation_key="shadow_updated",
        name="Shadow last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("timestamp")),
    ),
    AnthbotSensorDescription(
        key="system_boot_time",
        translation_key="system_boot_time",
        name="System boot time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("system_boot_time")),
    ),
    AnthbotSensorDescription(
        key="map_last_updated",
        translation_key="map_last_updated",
        name="Map last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("map_time")),
    ),
    AnthbotSensorDescription(
        key="path_last_updated",
        translation_key="path_last_updated",
        name="Path last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("path_time")),
    ),
    AnthbotSensorDescription(
        key="area_last_updated",
        translation_key="area_last_updated",
        name="Area last updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("area_time")),
    ),
    AnthbotSensorDescription(
        key="next_appointment",
        translation_key="next_appointment",
        name="Next appointment",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _as_datetime(data.get("appointment_time")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot sensors from config entry."""

    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]

    entities = [
        AnthbotSensorEntity(coordinator, description)
        for coordinator in coordinators
        for description in SENSORS
    ]

    entities.extend(
        AnthbotMapSensorEntity(coordinator)
        for coordinator in coordinators
    )

    async_add_entities(entities)


class AnthbotSensorEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SensorEntity
):
    """Anthbot sensor entity."""

    entity_description: AnthbotSensorDescription
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset(
        {"latest_task_event", "task_events", "task_events_error"}
    )

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotSensorDescription,
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
    def native_value(self) -> Any:
        """Return current sensor value."""
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
        rain_continue_time = state.get("rain_continue_time")
        mower_status = _general_mower_status(state)
        robot_status_raw = _raw_robot_status(state)
        attributes = {
            "serial_number": self.coordinator.client.serial_number,
            "mower_status": mower_status,
            "robot_status_raw": robot_status_raw,
            "cutting_height": cutting_height,
            "mowing_time": mowing_time,
            "mowing_area": mowing_area,
            "custom_mowing_direction": custom_mowing_direction,
            "custom_mowing_direction_enabled": custom_mowing_direction_enabled,
            "voice_volume": voice_volume,
            "voice_status": voice_status,
            "rain_continue_time": rain_continue_time,
        }
        if self.entity_description.key == "zones":
            manual_zone_list = manual_zones(state)
            attributes["zone_ids"] = [
                zone_id
                for zone in manual_zone_list
                if isinstance((zone_id := zone.get("id")), int)
            ]
            attributes["zone_names"] = [
                zone_name
                for zone in manual_zone_list
                if isinstance((zone_name := zone.get("name")), str) and zone_name
            ]
            attributes["active_zone_ids"] = active_manual_zone_ids(state)
        if self.entity_description.key == "auto_zones":
            auto_zone_list = auto_zones(state)
            attributes["auto_zone_ids"] = [
                zone_id
                for zone in auto_zone_list
                if isinstance((zone_id := zone.get("id")), int)
            ]
            attributes["auto_zone_names"] = [
                zone_name
                for zone in auto_zone_list
                if isinstance((zone_name := zone.get("name")), str) and zone_name
            ]

        if self.entity_description.key == "cloud_task_event_code":
            payload = state.get("_task_events")
            attributes["latest_task_event"] = latest_task_event(payload)
            attributes["task_events"] = task_event_items(payload)
            attributes["task_events_error"] = state.get("_task_events_error")
        return attributes
        
class AnthbotMapSensorEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SensorEntity
):
    """Anthbot map entity."""

    _unrecorded_attributes = frozenset(
        {
            "pose",
            "serial_number",
            "mower_status",
            "robot_status_raw",
            "cur_pose",
            "map_scan_pose",
            "path",
            "cloud_path",
            "mowed_path",
            "path_id",
            "path_start",
            "path_task_type",
            "path_point_count",
            "path_coordinate_scale",
            "path_first_point",
            "map_time",
            "path_time",
            "area_time",
            "ridable_area_time",
            "history_path_info",
            "history_path_source",
            "history_path_live_refresh",
            "history_path_refresh_interval",
            "history_path_download_source",
            "area_definition",
            "ridable_areas",
            "ridable_area_error",
            "map_definition_status",
            "path_definition_status",
            "map_raster",
            "map_definition_preview",
            "map_archive_selection",
            "path_definition_preview",
            "path_point_types",
            "map_binary_paths",
            "path_binary_paths",
            "map_definition_error",
            "path_definition_error",
            "cloud_connected",
            "cloud_last_success",
            "cloud_error",
            "robot_online",
            "live_shadow_connected",
            "live_shadow_error",
            "last_mowing_task",
            "custom_button_actions_configured",
            "custom_button_actions_enabled",
            "custom_button_actions",
            "mowing_records",
            "mowing_records_error",
            "task_events",
            "task_events_error",
            "error_history",
            "maintenance",
        }
    )
    _attr_has_entity_name = True
    _attr_name = "Map"
    _attr_icon = "mdi:map"

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)

        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_map"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def native_value(self) -> str:
        return "ready"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.reported_state
        map_definition = state.get("_map_definition")
        path_definition = state.get("_path_definition")
        path_points = _definition_path_points(path_definition) or state.get("path")

        return {
            "serial_number": self.coordinator.client.serial_number,
            "pose": state.get("pose"),
            "mower_status": _general_mower_status(state),
            "robot_status_raw": _raw_robot_status(state),
            "cur_pose": state.get("curPose") or state.get("cur_pose"),
            "map_scan_pose": state.get("mapScanPose") or state.get("map_scan_pose"),
            "path": path_points,
            "cloud_path": path_points,
            "mowed_path": path_points,
            "path_id": path_definition.get("path_id") if isinstance(path_definition, dict) else None,
            "path_start": path_definition.get("start") if isinstance(path_definition, dict) else None,
            "path_task_type": path_definition.get("task_type") if isinstance(path_definition, dict) else None,
            "path_point_count": path_definition.get("point_count") if isinstance(path_definition, dict) else None,
            "path_coordinate_scale": path_definition.get("coordinate_scale") if isinstance(path_definition, dict) else None,
            "path_first_point": _definition_path_first_point(path_definition),
            "map_time": state.get("map_time"),
            "path_time": state.get("path_time"),
            "area_time": state.get("area_time"),
            "ridable_area_time": state.get("ridable_area_time"),
            "history_path_info": state.get("_history_path_info"),
            "history_path_source": state.get("_history_path_source"),
            "history_path_live_refresh": state.get("_history_path_live_refresh"),
            "history_path_refresh_interval": state.get("_history_path_refresh_interval"),
            "history_path_download_source": path_definition.get("_download_source") if isinstance(path_definition, dict) else None,
            "area_definition": state.get("_area_definition"),
            "ridable_areas": ridable_areas(state),
            "ridable_area_error": state.get("_ridable_area_definition_error"),
            "map_definition_status": _definition_status(map_definition),
            "path_definition_status": _definition_status(path_definition),
            "map_raster": _definition_map_raster(map_definition),
            "map_definition_preview": _definition_preview(map_definition),
            "map_archive_selection": state.get("_map_archive_selection"),
            "path_definition_preview": _definition_preview(path_definition),
            "path_point_types": _definition_path_type_counts(path_definition),
            "map_binary_paths": _definition_binary_paths(map_definition),
            "path_binary_paths": _definition_binary_paths(path_definition),
            "map_definition_error": state.get("_map_definition_error"),
            "path_definition_error": state.get("_path_definition_error"),
            "cloud_connected": state.get("_cloud_connected"),
            "cloud_last_success": state.get("_cloud_last_success"),
            "cloud_error": state.get("_cloud_error"),
            "robot_online": state.get("_robot_online"),
            "live_shadow_connected": state.get("_live_shadow_connected", False),
            "live_shadow_error": state.get("_live_shadow_error"),
            "last_mowing_task": self.coordinator.last_mowing_task,
            "custom_button_actions_configured": self.coordinator.custom_button_actions_configured,
            "custom_button_actions_enabled": self.coordinator.custom_button_actions_enabled,
            "custom_button_actions": self.coordinator.custom_button_actions,
            "mowing_records": state.get("_mowing_records", {"data": []}),
            "mowing_records_error": state.get("_mowing_records_error"),
            "task_events": task_event_items(state.get("_task_events")),
            "task_events_error": state.get("_task_events_error"),
            "error_history": state.get("_error_history", []),
            "maintenance": state.get("robot_maintenance") or {
                "blade": state.get("cutting_components_life"),
                "camera": state.get("camera_life"),
                "charging_contact": state.get("recharge_contact_life"),
            },
        }        


def _definition_status(value: Any) -> str:
    if isinstance(value, dict):
        return f"dict:{len(value)}"
    if isinstance(value, list):
        return f"list:{len(value)}"
    if value is None:
        return "not_loaded"
    return type(value).__name__


def _definition_preview(value: Any) -> Any:
    if isinstance(value, dict):
        if isinstance(value.get("_binary_probe"), dict):
            return value["_binary_probe"]
        preview: dict[str, Any] = {"keys": [str(key) for key in list(value.keys())[:20]]}
        for key, child in list(value.items())[:8]:
            preview[str(key)] = _small_shape(child)
        return preview
    if isinstance(value, list):
        return {
            "length": len(value),
            "first": _small_shape(value[0]) if value else None,
        }
    return None


def _definition_map_raster(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    raster = value.get("_map_raster")
    if isinstance(raster, dict):
        return raster
    return None


def _definition_path_points(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    points = value.get("_path_points")
    if not isinstance(points, list):
        return []
    return [point for point in points if isinstance(point, dict)]


def _definition_path_first_point(value: Any) -> dict[str, Any] | None:
    points = _definition_path_points(value)
    return points[0] if points else None


def _definition_path_type_counts(value: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for point in _definition_path_points(value):
        point_type = str(point.get("type", "missing"))
        counts[point_type] = counts.get(point_type, 0) + 1
    return counts


def _small_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {"type": "dict", "keys": [str(key) for key in list(value.keys())[:10]]}
    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
            "first": _small_shape(value[0]) if value else None,
        }
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return type(value).__name__


def _definition_binary_paths(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    probe = value.get("_binary_probe")
    if not isinstance(probe, dict):
        return []
    paths = probe.get("coordinate_paths")
    if not isinstance(paths, list):
        return []
    compact: list[dict[str, Any]] = []
    for path in paths[:4]:
        if not isinstance(path, dict):
            continue
        points = path.get("points")
        if not isinstance(points, list) or len(points) < 3:
            continue
        compact.append(
            {
                "encoding": path.get("encoding"),
                "offset": path.get("offset"),
                "count": path.get("count"),
                "bounds": path.get("bounds"),
                "points": points,
            }
        )
    return compact
