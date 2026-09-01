"""Anthbot Genie integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from pathlib import Path
import shutil

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import (
    LOVELACE_DATA,
    MODE_STORAGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .api import AnthbotCloudApiClient, AnthbotGenieApiError, AnthbotShadowApiClient
from .const import (
    ATTR_AUTO_ZONES,
    ATTR_ENABLE_CUSTOM_DIRECTION,
    ATTR_ENABLE_RAIN_PERCEPTION,
    ATTR_EDGE_ID,
    ATTR_MOW_DIRECTION,
    ATTR_MOW_HEIGHT,
    ATTR_RAIN_CONTINUE_TIME,
    ATTR_RIDE_DISTANCE,
    ATTR_SERIAL_NUMBER,
    ATTR_VOICE_VOLUME,
    ATTR_ZONES,
    CONF_API_HOST,
    CONF_AREA_CODE,
    CONF_BEARER_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_BATTERY_SAVER_CONFIGS,
    CONF_CUSTOM_BUTTON_CONFIGS,
    CONF_CHARGE_LIMIT,
    CONF_CHARGER_SWITCH,
    CONF_MAINTENANCE_LEVEL,
    CONF_RESUME_LEVEL,
    CONF_SHARED_RTK_POWER,
    CONF_USERNAME,
    DEFAULT_AREA_CODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_CONNECT_CLOUD,
    SERVICE_RETURN_TO_DOCK,
    SERVICE_START_AUTO_ZONE_MOW,
    SERVICE_SET_CUSTOM_MOWING_DIRECTION,
    SERVICE_SET_EDGE_SETTINGS,
    SERVICE_SET_MOW_HEIGHT,
    SERVICE_SET_RAIN_CONTINUE_TIME,
    SERVICE_SET_RAIN_PERCEPTION,
    SERVICE_SET_VOICE_VOLUME,
    SERVICE_START_FULL_MOW,
    SERVICE_START_OUTER_EDGE_MOW,
    SERVICE_START_DOCK_EDGE_MOW,
    SERVICE_START_ZONE_MOW,
    SERVICE_STOP_MOW,
    SERVICE_PAUSE_MOW,
    SERVICE_RESUME_MOW,
    SERVICE_RESET_BLADE_MAINTENANCE,
    SERVICE_RESET_CAMERA_MAINTENANCE,
    SERVICE_RESET_DOCK_CONTACT_MAINTENANCE,
    SERVICE_GET_MOWING_RECORD_DETAIL,
    SERVICE_SET_BATTERY_SAVER_CONFIG,
    SERVICE_SET_CUSTOM_BUTTON_ACTIONS,
)
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .commands import (
    async_prepare_cloud_connection,
    async_start_mowing,
    async_start_outer_edge_mowing,
)
from .zones import async_update_edge_settings, auto_zones, manual_zones

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    "sensor",
    "binary_sensor",
    "button",
    "number",
    "switch",
    "device_tracker",
    "lawn_mower",
]
_LOGGER = logging.getLogger(__name__)
VALID_MOW_HEIGHTS = list(range(30, 75, 5))
FRONTEND_RESOURCE_PATH = "/anthbot-map-v2/anthbot-map-card.js"
FRONTEND_RESOURCE_URL = f"{FRONTEND_RESOURCE_PATH}?v=2.4.3-beta.2"
LEGACY_ENTITY_SUFFIXES: tuple[str, ...] = (
    "enable_custom_mowing_direction",
    "custom_mowing_direction_enable",
    "custom_mowing_direction_enabled_button",
    "mow_count",
    "last_service_command_state",
    "mowing_progress_source",
    "mowing_finish_cause",
    "mowing_incomplete",
)


def _all_coordinators(hass: HomeAssistant) -> list[AnthbotGenieDataUpdateCoordinator]:
    entries = hass.data.get(DOMAIN, {})
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = []
    for entry_coordinators in entries.values():
        coordinators.extend(entry_coordinators)
    return coordinators


def _resolve_target_coordinators(
    hass: HomeAssistant, service_data: dict
) -> list[AnthbotGenieDataUpdateCoordinator]:
    coordinators = _all_coordinators(hass)
    if not coordinators:
        return []

    requested_serials: set[str] = set()
    target_requested = False

    serial_value = service_data.get(ATTR_SERIAL_NUMBER)
    if isinstance(serial_value, str) and serial_value:
        target_requested = True
        requested_serials.add(serial_value)
    elif isinstance(serial_value, list):
        target_requested = bool(serial_value)
        requested_serials.update(
            item for item in serial_value if isinstance(item, str) and item
        )

    entity_ids = service_data.get("entity_id")
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    if isinstance(entity_ids, list):
        target_requested = target_requested or bool(entity_ids)
        for entity_id in entity_ids:
            if not isinstance(entity_id, str):
                continue
            state = hass.states.get(entity_id)
            if state is None:
                continue
            serial_number = state.attributes.get(ATTR_SERIAL_NUMBER)
            if isinstance(serial_number, str) and serial_number:
                requested_serials.add(serial_number)

    if not requested_serials:
        # A service call without a target intentionally applies to every mower.
        # If a target was supplied but could not be resolved, never fall back to
        # every mower: doing so could run the action against the wrong device in
        # a multi-mower account.
        return [] if target_requested else coordinators

    return [
        coordinator
        for coordinator in coordinators
        if coordinator.client.serial_number in requested_serials
    ]


def _normalize_zone_selector(value: object) -> list[str | int]:
    selectors: list[str | int] = []
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        for item in value.split(","):
            candidate = item.strip()
            if not candidate:
                continue
            if candidate.isdigit():
                selectors.append(int(candidate))
            else:
                selectors.append(candidate)
        return selectors
    if isinstance(value, list):
        for item in value:
            selectors.extend(_normalize_zone_selector(item))
    return selectors


def _resolve_manual_zone_ids(
    coordinator: AnthbotGenieDataUpdateCoordinator, selectors: list[str | int]
) -> list[int]:
    zones = manual_zones(coordinator.reported_state)
    by_id = {
        zone_id: zone
        for zone in zones
        if isinstance((zone_id := zone.get("id")), int)
    }
    by_name = {
        zone_name.casefold(): zone
        for zone in zones
        if isinstance((zone_name := zone.get("name")), str) and zone_name
    }

    resolved: list[int] = []
    for selector in selectors:
        zone: dict | None = None
        if isinstance(selector, int):
            zone = by_id.get(selector)
        elif isinstance(selector, str):
            zone = by_name.get(selector.casefold())
            if zone is None and selector.isdigit():
                zone = by_id.get(int(selector))
        zone_id = zone.get("id") if isinstance(zone, dict) else None
        if isinstance(zone_id, int) and zone_id not in resolved:
            resolved.append(zone_id)
    return resolved


def _resolve_auto_zone_points(
    coordinator: AnthbotGenieDataUpdateCoordinator, selectors: list[str | int]
) -> list[list[int]]:
    zones = auto_zones(coordinator.reported_state)
    by_id = {
        zone_id: zone
        for zone in zones
        if isinstance((zone_id := zone.get("id")), int)
    }
    by_name = {
        zone_name.casefold(): zone
        for zone in zones
        if isinstance((zone_name := zone.get("name")), str) and zone_name
    }

    resolved: list[list[int]] = []
    for selector in selectors:
        zone: dict | None = None
        if isinstance(selector, int):
            zone = by_id.get(selector)
        elif isinstance(selector, str):
            zone = by_name.get(selector.casefold())
            if zone is None and selector.isdigit():
                zone = by_id.get(int(selector))

        if not isinstance(zone, dict):
            continue
        x = zone.get("x")
        y = zone.get("y")
        if isinstance(x, int) and isinstance(y, int):
            point = [x, y]
            if point not in resolved:
                resolved.append(point)
    return resolved


_CUSTOM_BUTTON_COMMANDS = {
    "start",
    "stop",
    "dock",
    "pause",
    "resume",
    "outer-edge",
    "dock-edge",
    "connect",
    "reset-blade",
    "reset-camera",
    "reset-contact",
}


def _normalize_custom_button_actions(value: object) -> dict[str, dict]:
    """Validate and normalize custom card-button service definitions."""
    if not isinstance(value, dict):
        raise AnthbotGenieApiError("Custom button actions must be an object")

    normalized: dict[str, dict] = {}
    for raw_command, raw_action in value.items():
        command = str(raw_command)
        if command not in _CUSTOM_BUTTON_COMMANDS:
            raise AnthbotGenieApiError(f"Unsupported custom button command: {command}")

        if isinstance(raw_action, str):
            action: dict = {"service": raw_action}
        elif isinstance(raw_action, dict):
            action = dict(raw_action)
        else:
            raise AnthbotGenieApiError(
                f"Invalid custom action definition for {command}"
            )

        service = action.get("service")
        if not isinstance(service, str):
            raise AnthbotGenieApiError(
                f"Custom action for {command} must contain domain.service"
            )
        service = service.strip()
        if "." not in service:
            raise AnthbotGenieApiError(
                f"Custom action for {command} must contain domain.service"
            )
        domain, service_name = service.split(".", 1)
        if not domain or not service_name:
            raise AnthbotGenieApiError(
                f"Custom action for {command} must contain domain.service"
            )

        definition: dict = {"service": service}
        target = action.get("target")
        if target is not None:
            if not isinstance(target, dict):
                raise AnthbotGenieApiError(
                    f"Custom action target for {command} must be an object"
                )
            definition["target"] = dict(target)
        data = action.get("data", action.get("service_data"))
        if data is not None:
            if not isinstance(data, dict):
                raise AnthbotGenieApiError(
                    f"Custom action data for {command} must be an object"
                )
            definition["data"] = dict(data)
        normalized[command] = definition

    return normalized


async def _async_register_services(hass: HomeAssistant) -> None:
    async def _async_sync_after_command(
        coordinator: AnthbotGenieDataUpdateCoordinator,
    ) -> None:
        async def _async_refresh_later() -> None:
            await asyncio.sleep(0.35)
            await coordinator.client.async_request_all_properties()
            await coordinator.async_request_refresh()

        hass.async_create_task(_async_refresh_later())

    async def _async_sync_now(
        coordinator: AnthbotGenieDataUpdateCoordinator,
    ) -> None:
        await coordinator.client.async_request_all_properties()
        await coordinator.async_request_refresh()

    base_schema = vol.Schema(
        {
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    set_height_schema = vol.Schema(
        {
            vol.Required(ATTR_MOW_HEIGHT): vol.In(VALID_MOW_HEIGHTS),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    set_edge_settings_schema = vol.Schema(
        {
            vol.Required(ATTR_EDGE_ID): vol.Coerce(int),
            vol.Required(ATTR_MOW_HEIGHT): vol.In(VALID_MOW_HEIGHTS),
            vol.Required(ATTR_RIDE_DISTANCE): vol.In((5, 7, 10, 13, 15, 17, 20)),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    set_voice_volume_schema = vol.Schema(
        {
            vol.Required(ATTR_VOICE_VOLUME): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    set_custom_mowing_direction_schema = vol.Schema(
        {
            vol.Required(ATTR_MOW_DIRECTION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=180)
            ),
            vol.Optional(ATTR_ENABLE_CUSTOM_DIRECTION, default=True): cv.boolean,
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    set_rain_continue_time_schema = vol.Schema(
        {
            vol.Required(ATTR_RAIN_CONTINUE_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=8)
            ),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    set_rain_perception_schema = vol.Schema(
        {
            vol.Required(ATTR_ENABLE_RAIN_PERCEPTION): cv.boolean,
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    battery_saver_config_schema = vol.Schema(
        {
            vol.Optional(CONF_CHARGER_SWITCH): cv.entity_id,
            vol.Required(CONF_CHARGE_LIMIT): vol.All(
                vol.Coerce(int), vol.Range(min=20, max=100)
            ),
            vol.Required(CONF_MAINTENANCE_LEVEL): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=99)
            ),
            vol.Required(CONF_RESUME_LEVEL): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=99)
            ),
            vol.Required(CONF_SHARED_RTK_POWER, default=False): cv.boolean,
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    custom_button_actions_schema = vol.Schema(
        {
            vol.Required("enabled"): cv.boolean,
            vol.Required("actions"): dict,
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    zone_schema = vol.Schema(
        {
            vol.Required(ATTR_ZONES): vol.Any(
                vol.Coerce(int), cv.string, [vol.Any(vol.Coerce(int), cv.string)]
            ),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    auto_zone_schema = vol.Schema(
        {
            vol.Required(ATTR_AUTO_ZONES): vol.Any(
                vol.Coerce(int), cv.string, [vol.Any(vol.Coerce(int), cv.string)]
            ),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    mowing_record_detail_schema = vol.Schema(
        {
            vol.Optional("area_url"): cv.string,
            vol.Optional("map_url"): cv.string,
            vol.Optional("path_url"): cv.string,
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    async def _handle_start_full_mow(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            if await async_start_mowing(coordinator, app_state=1):
                coordinator.remember_mowing_task("full")
            await _async_sync_after_command(coordinator)

    async def _handle_start_outer_edge_mow(service_call) -> None:
        for coordinator in _resolve_target_coordinators(hass, service_call.data):
            if await async_start_outer_edge_mowing(coordinator):
                coordinator.remember_mowing_task("edge")
            await _async_sync_after_command(coordinator)

    async def _handle_start_dock_edge_mow(service_call) -> None:
        for coordinator in _resolve_target_coordinators(hass, service_call.data):
            if not await async_prepare_cloud_connection(coordinator, mowing_start=True):
                _LOGGER.warning(
                    "Anthbot mower %s did not confirm the wake request; "
                    "attempting dock mowing on the live MQTT transport",
                    coordinator.client.serial_number,
                )
            await coordinator.client.async_publish_service_command(cmd="nest_mow_start", data=1)
            coordinator.remember_mowing_task("dock_edge")
            await _async_sync_after_command(coordinator)

    async def _handle_connect_cloud(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            connected = await async_prepare_cloud_connection(
                coordinator, attempts=3, wait_seconds=5
            )
            if not connected:
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection"
                )

    async def _handle_stop_mow(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_prepare_cloud_connection(coordinator)
            await coordinator.client.async_publish_service_command(cmd="stop_all_tasks")
            await coordinator.async_clear_last_mowing_task()
            await _async_sync_after_command(coordinator)

    async def _handle_pause_mow(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_prepare_cloud_connection(coordinator)
            await coordinator.client.async_publish_service_command(cmd="mow_pause")
            await _async_sync_after_command(coordinator)

    async def _handle_resume_mow(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            task = coordinator.last_mowing_task
            if task is None:
                raise AnthbotGenieApiError(
                    "There is no mowing task to resume; start a new task"
                )
            task_type = task["type"]
            data = task.get("data")
            if task_type == "full":
                started = await async_start_mowing(coordinator, app_state=1)
            elif task_type == "edge":
                started = await async_start_outer_edge_mowing(coordinator)
            elif task_type == "dock_edge":
                await async_prepare_cloud_connection(coordinator, mowing_start=True)
                await coordinator.client.async_publish_service_command(
                    cmd="nest_mow_start", data=1
                )
                started = True
            else:
                if not await async_prepare_cloud_connection(
                    coordinator, mowing_start=True
                ):
                    raise AnthbotGenieApiError(
                        "The mower did not confirm its cloud connection"
                    )
                command = (
                    "custom_area_mow_start"
                    if task_type == "manual_zone"
                    else "region_mow_start"
                )
                await coordinator.client.async_publish_service_command(
                    cmd=command, data=data
                )
                started = True
            if not started:
                raise AnthbotGenieApiError(
                    "The mower did not confirm resuming the mowing task"
                )
            await _async_sync_after_command(coordinator)

    async def _handle_reset_maintenance(service_call, reset_id: int) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_prepare_cloud_connection(coordinator)
            await coordinator.client.async_publish_service_command(
                cmd="robot_maintenance_reset", data={"reset_id": reset_id}
            )
            await _async_sync_after_command(coordinator)

    async def _handle_reset_blade_maintenance(service_call) -> None:
        await _handle_reset_maintenance(service_call, 1)

    async def _handle_reset_camera_maintenance(service_call) -> None:
        await _handle_reset_maintenance(service_call, 2)

    async def _handle_reset_dock_contact_maintenance(service_call) -> None:
        await _handle_reset_maintenance(service_call, 0)

    async def _handle_get_mowing_record_detail(service_call) -> dict:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        coordinator = targets[0]
        return await coordinator.account_client.async_get_mowing_record_detail(
            coordinator.client.serial_number,
            area_url=service_call.data.get("area_url"),
            map_url=service_call.data.get("map_url"),
            path_url=service_call.data.get("path_url"),
        )

    async def _handle_return_to_dock(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_prepare_cloud_connection(coordinator)
            await coordinator.client.async_publish_service_command(cmd="charge_start")
            await _async_sync_after_command(coordinator)

    async def _handle_set_mow_height(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        mow_height = int(service_call.data[ATTR_MOW_HEIGHT])
        for coordinator in targets:
            await coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={"cutter_height": mow_height},
            )
            await _async_sync_after_command(coordinator)

    async def _handle_set_edge_settings(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_prepare_cloud_connection(coordinator)
            await async_update_edge_settings(
                coordinator,
                edge_id=int(service_call.data[ATTR_EDGE_ID]),
                cutter_height=int(service_call.data[ATTR_MOW_HEIGHT]),
                ride_distance=int(service_call.data[ATTR_RIDE_DISTANCE]),
            )

    async def _handle_set_voice_volume(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        voice_volume = int(service_call.data[ATTR_VOICE_VOLUME])
        for coordinator in targets:
            await coordinator.client.async_publish_service_command(
                cmd="volume_ctl",
                data={"volume": voice_volume},
            )
            await _async_sync_after_command(coordinator)

    async def _handle_set_custom_mowing_direction(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        mow_direction = int(service_call.data[ATTR_MOW_DIRECTION])
        enable_custom_direction = bool(
            service_call.data.get(ATTR_ENABLE_CUSTOM_DIRECTION, True)
        )
        for coordinator in targets:
            await coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={
                    "mow_head": mow_direction,
                    "enable_adaptive_head": 0 if enable_custom_direction else 1,
                },
            )
            await _async_sync_after_command(coordinator)

    async def _handle_set_rain_continue_time(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        rain_continue_time = int(service_call.data[ATTR_RAIN_CONTINUE_TIME])
        for coordinator in targets:
            rain_switch = coordinator.reported_state.get("rain_switch")
            switch_value = 1 if rain_switch in (1, "1", True, "true", "on") else 0
            await coordinator.client.async_publish_service_command(
                cmd="ctl_rainer",
                data={
                    "switch": switch_value,
                    "continue_time": rain_continue_time * 3600,
                },
            )
            await _async_sync_after_command(coordinator)

    async def _handle_set_rain_perception(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        enabled = bool(service_call.data[ATTR_ENABLE_RAIN_PERCEPTION])
        for coordinator in targets:
            reported_continue_time = coordinator.reported_state.get("rain_continue_time")
            continue_time = (
                reported_continue_time
                if isinstance(reported_continue_time, int) and reported_continue_time > 0
                else 10800
            )
            await coordinator.client.async_publish_service_command(
                cmd="ctl_rainer",
                data={
                    "switch": 1 if enabled else 0,
                    "continue_time": continue_time,
                },
            )
            await _async_sync_after_command(coordinator)

    async def _handle_set_battery_saver_config(service_call) -> None:
        charge_limit = int(service_call.data[CONF_CHARGE_LIMIT])
        maintenance_level = int(service_call.data[CONF_MAINTENANCE_LEVEL])
        resume_level = int(service_call.data[CONF_RESUME_LEVEL])
        if maintenance_level >= charge_limit or resume_level >= charge_limit:
            raise AnthbotGenieApiError(
                "Maintenance and resume levels must be lower than the charge limit"
            )
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        target_serials = {item.client.serial_number for item in targets}
        for entry_id, coordinators in hass.data.get(DOMAIN, {}).items():
            matching = [
                item
                for item in coordinators
                if item.client.serial_number in target_serials
            ]
            if not matching:
                continue
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            options = dict(entry.options)
            stored = options.get(CONF_BATTERY_SAVER_CONFIGS, {})
            configs = dict(stored) if isinstance(stored, dict) else {}
            for coordinator in matching:
                previous = configs.get(coordinator.client.serial_number, {})
                config = dict(previous) if isinstance(previous, dict) else {}
                config.update(
                    {
                        CONF_CHARGER_SWITCH: service_call.data.get(
                            CONF_CHARGER_SWITCH,
                            coordinator.battery_saver_config.get(CONF_CHARGER_SWITCH),
                        ),
                        CONF_CHARGE_LIMIT: charge_limit,
                        CONF_MAINTENANCE_LEVEL: maintenance_level,
                        CONF_RESUME_LEVEL: resume_level,
                        CONF_SHARED_RTK_POWER: bool(
                            service_call.data[CONF_SHARED_RTK_POWER]
                        ),
                    }
                )
                configs[coordinator.client.serial_number] = config
            options[CONF_BATTERY_SAVER_CONFIGS] = configs
            hass.config_entries.async_update_entry(entry, options=options)
            await _async_update_entry_options(hass, entry)

    async def _handle_set_custom_button_actions(service_call) -> None:
        enabled = bool(service_call.data["enabled"])
        actions = _normalize_custom_button_actions(service_call.data["actions"])
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        target_serials = {item.client.serial_number for item in targets}
        for entry_id, coordinators in hass.data.get(DOMAIN, {}).items():
            matching = [
                item
                for item in coordinators
                if item.client.serial_number in target_serials
            ]
            if not matching:
                continue
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None:
                continue
            options = dict(entry.options)
            stored = options.get(CONF_CUSTOM_BUTTON_CONFIGS, {})
            configs = dict(stored) if isinstance(stored, dict) else {}
            for coordinator in matching:
                configs[coordinator.client.serial_number] = {
                    "configured": True,
                    "enabled": enabled,
                    "actions": actions,
                }
            options[CONF_CUSTOM_BUTTON_CONFIGS] = configs
            hass.config_entries.async_update_entry(entry, options=options)
            await _async_update_entry_options(hass, entry)

    async def _handle_start_zone_mow(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        selectors = _normalize_zone_selector(service_call.data[ATTR_ZONES])
        for coordinator in targets:
            zone_ids = _resolve_manual_zone_ids(coordinator, selectors)
            if not zone_ids:
                raise AnthbotGenieApiError(
                    f"No matching zones found for mower {coordinator.client.serial_number}"
                )
            if not await async_prepare_cloud_connection(coordinator, mowing_start=True):
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection; zone mowing was not started"
                )
            await coordinator.client.async_publish_service_command(
                cmd="custom_area_mow_start",
                data={"id": zone_ids},
            )
            coordinator.remember_mowing_task("manual_zone", {"id": zone_ids})
            await _async_sync_after_command(coordinator)

    async def _handle_start_auto_zone_mow(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        selectors = _normalize_zone_selector(service_call.data[ATTR_AUTO_ZONES])
        for coordinator in targets:
            points = _resolve_auto_zone_points(coordinator, selectors)
            if not points:
                raise AnthbotGenieApiError(
                    f"No matching auto-zones found for mower {coordinator.client.serial_number}"
                )
            if not await async_prepare_cloud_connection(coordinator, mowing_start=True):
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection; auto-zone mowing was not started"
                )
            await coordinator.client.async_publish_service_command(
                cmd="region_mow_start",
                data={"points": points},
            )
            coordinator.remember_mowing_task("auto_zone", {"points": points})
            await _async_sync_after_command(coordinator)

    if not hass.services.has_service(DOMAIN, SERVICE_START_FULL_MOW):
        hass.services.async_register(
            DOMAIN,
            SERVICE_START_FULL_MOW,
            _handle_start_full_mow,
            schema=base_schema,
        )
    for service_name, handler in (
        (SERVICE_START_OUTER_EDGE_MOW, _handle_start_outer_edge_mow),
        (SERVICE_START_DOCK_EDGE_MOW, _handle_start_dock_edge_mow),
    ):
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(DOMAIN, service_name, handler, schema=base_schema)
    if not hass.services.has_service(DOMAIN, SERVICE_CONNECT_CLOUD):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CONNECT_CLOUD,
            _handle_connect_cloud,
            schema=base_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_STOP_MOW):
        hass.services.async_register(
            DOMAIN, SERVICE_STOP_MOW, _handle_stop_mow, schema=base_schema
        )
    if not hass.services.has_service(DOMAIN, SERVICE_PAUSE_MOW):
        hass.services.async_register(
            DOMAIN, SERVICE_PAUSE_MOW, _handle_pause_mow, schema=base_schema
        )
    if not hass.services.has_service(DOMAIN, SERVICE_RESUME_MOW):
        hass.services.async_register(
            DOMAIN, SERVICE_RESUME_MOW, _handle_resume_mow, schema=base_schema
        )
    if not hass.services.has_service(DOMAIN, SERVICE_RETURN_TO_DOCK):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RETURN_TO_DOCK,
            _handle_return_to_dock,
            schema=base_schema,
        )
    for service_name, handler in (
        (SERVICE_RESET_BLADE_MAINTENANCE, _handle_reset_blade_maintenance),
        (SERVICE_RESET_CAMERA_MAINTENANCE, _handle_reset_camera_maintenance),
        (SERVICE_RESET_DOCK_CONTACT_MAINTENANCE, _handle_reset_dock_contact_maintenance),
    ):
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(DOMAIN, service_name, handler, schema=base_schema)
    if not hass.services.has_service(DOMAIN, SERVICE_GET_MOWING_RECORD_DETAIL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_MOWING_RECORD_DETAIL,
            _handle_get_mowing_record_detail,
            schema=mowing_record_detail_schema,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_MOW_HEIGHT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_MOW_HEIGHT,
            _handle_set_mow_height,
            schema=set_height_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_EDGE_SETTINGS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_EDGE_SETTINGS,
            _handle_set_edge_settings,
            schema=set_edge_settings_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_VOICE_VOLUME):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_VOICE_VOLUME,
            _handle_set_voice_volume,
            schema=set_voice_volume_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_CUSTOM_MOWING_DIRECTION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CUSTOM_MOWING_DIRECTION,
            _handle_set_custom_mowing_direction,
            schema=set_custom_mowing_direction_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_RAIN_CONTINUE_TIME):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_RAIN_CONTINUE_TIME,
            _handle_set_rain_continue_time,
            schema=set_rain_continue_time_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_RAIN_PERCEPTION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_RAIN_PERCEPTION,
            _handle_set_rain_perception,
            schema=set_rain_perception_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_BATTERY_SAVER_CONFIG):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_BATTERY_SAVER_CONFIG,
            _handle_set_battery_saver_config,
            schema=battery_saver_config_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_CUSTOM_BUTTON_ACTIONS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CUSTOM_BUTTON_ACTIONS,
            _handle_set_custom_button_actions,
            schema=custom_button_actions_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_START_ZONE_MOW):
        hass.services.async_register(
            DOMAIN,
            SERVICE_START_ZONE_MOW,
            _handle_start_zone_mow,
            schema=zone_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_START_AUTO_ZONE_MOW):
        hass.services.async_register(
            DOMAIN,
            SERVICE_START_AUTO_ZONE_MOW,
            _handle_start_auto_zone_mow,
            schema=auto_zone_schema,
        )

def _async_cleanup_legacy_entities(
    hass: HomeAssistant, entry: ConfigEntry, serial_number: str
) -> None:
    """Remove legacy entities superseded or removed by integration updates."""
    entity_registry = er.async_get(hass)
    for entry_reg in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entry_reg.domain not in {"button", "binary_sensor", "sensor"}:
            continue
        unique_id = entry_reg.unique_id
        if not isinstance(unique_id, str):
            continue
        if not unique_id.startswith(f"{serial_number}_"):
            continue
        if any(unique_id.endswith(suffix) for suffix in LEGACY_ENTITY_SUFFIXES):
            entity_registry.async_remove(entry_reg.entity_id)


def _sync_standalone_frontend(source: Path, destination: Path) -> None:
    """Mirror the card into /config/www so it survives a disabled config entry."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Register the bundled card once in Lovelace storage mode."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None or getattr(lovelace, "resource_mode", None) != MODE_STORAGE:
        _LOGGER.info(
            "Anthbot Map card resource was not created because Lovelace resources "
            "are not stored in UI storage mode"
        )
        return

    resources = getattr(lovelace, "resources", None)
    if resources is None:
        _LOGGER.warning("Lovelace resource storage is unavailable")
        return

    # async_get_info() ensures the storage collection is loaded before items
    # are inspected or created. This preserves every existing dashboard resource.
    await resources.async_get_info()
    matching = [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).split("?", 1)[0]
        in {
            FRONTEND_RESOURCE_PATH,
            f"/local{FRONTEND_RESOURCE_PATH}",
        }
    ]
    if matching:
        current = matching[0]
        if (
            current.get("url") != FRONTEND_RESOURCE_URL
            or current.get("type") != "module"
        ):
            await resources.async_update_item(
                current["id"],
                {"res_type": "module", "url": FRONTEND_RESOURCE_URL},
            )
        if len(matching) > 1:
            _LOGGER.warning(
                "Multiple Anthbot Map Lovelace resources already exist; keeping "
                "them unchanged except for the first entry"
            )
        return

    await resources.async_create_item(
        {"res_type": "module", "url": FRONTEND_RESOURCE_URL}
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Anthbot Genie integration."""
    frontend_path = Path(__file__).parent / "frontend"
    standalone_path = Path(hass.config.path("www", "anthbot-map-v2"))
    await hass.async_add_executor_job(
        _sync_standalone_frontend, frontend_path, standalone_path
    )
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/anthbot-map-v2", str(frontend_path), False)]
    )
    try:
        await _async_register_lovelace_resource(hass)
    except Exception:  # noqa: BLE001 - frontend failure must not block the mower
        _LOGGER.exception("Unable to register the Anthbot Map Lovelace resource")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anthbot Genie from a config entry."""
    session = async_get_clientsession(hass)
    account_client = AnthbotCloudApiClient(
        session=session,
        host=entry.data[CONF_API_HOST],
        bearer_token=entry.data.get(CONF_BEARER_TOKEN),
    )

    try:
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        if isinstance(username, str) and isinstance(password, str):
            await account_client.async_login(
                username=username,
                password=password,
                area_code=str(entry.data.get(CONF_AREA_CODE, DEFAULT_AREA_CODE)),
            )
        devices = await account_client.async_get_bound_devices()
    except AnthbotGenieApiError as err:
        raise ConfigEntryNotReady(str(err)) from err
    if not devices:
        raise ConfigEntryNotReady("No Anthbot devices found for this account")

    entry.async_on_unload(entry.add_update_listener(_async_update_entry_options))
    battery_saver_configs = entry.options.get(CONF_BATTERY_SAVER_CONFIGS, {})
    if not isinstance(battery_saver_configs, dict):
        battery_saver_configs = {}
    custom_button_configs = entry.options.get(CONF_CUSTOM_BUTTON_CONFIGS, {})
    if not isinstance(custom_button_configs, dict):
        custom_button_configs = {}
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = []
    for device in devices:
        if device.is_owner is False:
            _LOGGER.warning(
                "Device %s (%s) is not owned by this account; control commands may be rejected with 403",
                device.alias,
                device.serial_number,
            )

        region_name: str | None = None
        iot_endpoint: str | None = None
        try:
            device_region = await account_client.async_get_device_region(
                device.serial_number
            )
            region_name = device_region.region_name
            iot_endpoint = device_region.iot_endpoint
        except AnthbotGenieApiError as err:
            _LOGGER.warning(
                "Failed to fetch region metadata for %s (%s), using defaults: %s",
                device.alias,
                device.serial_number,
                err,
            )

        try:
            fallback_region = await account_client.async_get_device_presigned_region(
                device.serial_number
            )
            if fallback_region:
                if not region_name:
                    region_name = fallback_region
                if not iot_endpoint and not fallback_region.startswith("cn"):
                    iot_endpoint = (
                        AnthbotShadowApiClient.build_default_iot_endpoint_for_region(
                            fallback_region
                        )
                    )
                elif iot_endpoint and not fallback_region.startswith("cn"):
                    endpoint_region = AnthbotShadowApiClient.guess_region_from_endpoint(
                        iot_endpoint
                    )
                    if endpoint_region and endpoint_region != fallback_region:
                        iot_endpoint = (
                            AnthbotShadowApiClient.build_default_iot_endpoint_for_region(
                                fallback_region
                            )
                        )
                        region_name = fallback_region
                        _LOGGER.debug(
                            "Overriding mismatched region metadata for %s (%s): fallback_region=%s endpoint=%s",
                            device.alias,
                            device.serial_number,
                            fallback_region,
                            iot_endpoint,
                        )
                _LOGGER.debug(
                    "Resolved region metadata for %s (%s): region=%s endpoint=%s",
                    device.alias,
                    device.serial_number,
                    region_name,
                    iot_endpoint,
                )
        except AnthbotGenieApiError as err:
            _LOGGER.debug(
                "Presigned-url fallback region lookup failed for %s (%s): %s",
                device.alias,
                device.serial_number,
                err,
            )

        shadow_client = AnthbotShadowApiClient(
            session=session,
            serial_number=device.serial_number,
            region_name=region_name,
            iot_endpoint=iot_endpoint,
            account_client=account_client,
        )
        _async_cleanup_legacy_entities(hass, entry, device.serial_number)
        # A previous clamp accidentally forced every configured value back to
        # at most ten seconds.  That is much more aggressive than the mobile
        # app and can make AWS IoT throttle the property shadow with HTTP 429.
        scan_interval = max(
            30,
            min(
                int(entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                3600,
            ),
        )
        coordinator = AnthbotGenieDataUpdateCoordinator(
            hass,
            account_client=account_client,
            client=shadow_client,
            device=device,
            update_interval=timedelta(seconds=scan_interval),
            battery_saver_config=battery_saver_configs.get(device.serial_number),
            custom_button_config=custom_button_configs.get(device.serial_number),
        )
        await coordinator.async_load_last_mowing_task()
        await coordinator.async_load_battery_saver_state()
        await coordinator.async_load_mowing_area_learning()
        # The mobile app establishes the named-shadow MQTT session first.
        # Ancillary REST data can refresh independently afterwards.
        await coordinator.async_start_live_shadow()
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            _LOGGER.warning(
                "Initial refresh failed for %s (%s): %s",
                device.alias,
                device.serial_number,
                coordinator.last_exception,
            )
        coordinators.append(coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for coordinator in coordinators:
        coordinator.start_battery_saver_monitor()
    return True


async def _async_update_entry_options(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Apply per-mower options without unloading the live integration."""
    battery_configs = entry.options.get(CONF_BATTERY_SAVER_CONFIGS, {})
    if not isinstance(battery_configs, dict):
        battery_configs = {}
    custom_button_configs = entry.options.get(CONF_CUSTOM_BUTTON_CONFIGS, {})
    if not isinstance(custom_button_configs, dict):
        custom_button_configs = {}
    coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id, [])
    for coordinator in coordinators:
        battery_config = battery_configs.get(coordinator.client.serial_number)
        await coordinator.async_update_battery_saver_config(
            battery_config if isinstance(battery_config, dict) else {}
        )
        custom_button_config = custom_button_configs.get(coordinator.client.serial_number)
        await coordinator.async_update_custom_button_config(
            custom_button_config if isinstance(custom_button_config, dict) else {}
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Anthbot Genie config entry without tearing down a failed unload."""
    coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id, [])
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    for coordinator in coordinators:
        await coordinator.async_stop_battery_saver_monitor()
        await coordinator.async_stop_live_shadow()

    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        for service_name in (
            SERVICE_START_FULL_MOW,
            SERVICE_START_OUTER_EDGE_MOW,
            SERVICE_START_DOCK_EDGE_MOW,
            SERVICE_STOP_MOW,
            SERVICE_PAUSE_MOW,
            SERVICE_RESUME_MOW,
            SERVICE_RETURN_TO_DOCK,
            SERVICE_SET_MOW_HEIGHT,
            SERVICE_SET_EDGE_SETTINGS,
            SERVICE_SET_VOICE_VOLUME,
            SERVICE_SET_CUSTOM_MOWING_DIRECTION,
            SERVICE_CONNECT_CLOUD,
            SERVICE_SET_RAIN_CONTINUE_TIME,
            SERVICE_SET_RAIN_PERCEPTION,
            SERVICE_START_ZONE_MOW,
            SERVICE_START_AUTO_ZONE_MOW,
            SERVICE_RESET_BLADE_MAINTENANCE,
            SERVICE_RESET_CAMERA_MAINTENANCE,
            SERVICE_RESET_DOCK_CONTACT_MAINTENANCE,
            SERVICE_GET_MOWING_RECORD_DETAIL,
            SERVICE_SET_BATTERY_SAVER_CONFIG,
            SERVICE_SET_CUSTOM_BUTTON_ACTIONS,
        ):
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
    return True
