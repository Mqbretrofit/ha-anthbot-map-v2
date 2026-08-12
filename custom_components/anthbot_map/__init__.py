"""Anthbot Genie integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from pathlib import Path
import shutil

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .api import AnthbotCloudApiClient, AnthbotGenieApiError, AnthbotShadowApiClient
from .const import (
    ATTR_AUTO_ZONES,
    ATTR_ENABLE_CUSTOM_DIRECTION,
    ATTR_ENABLE_RAIN_PERCEPTION,
    ATTR_MOW_DIRECTION,
    ATTR_MOW_HEIGHT,
    ATTR_RAIN_CONTINUE_TIME,
    ATTR_SERIAL_NUMBER,
    ATTR_VOICE_VOLUME,
    ATTR_ZONES,
    CONF_API_HOST,
    CONF_AREA_CODE,
    CONF_BEARER_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_AREA_CODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_CONNECT_CLOUD,
    SERVICE_RETURN_TO_DOCK,
    SERVICE_START_AUTO_ZONE_MOW,
    SERVICE_SET_CUSTOM_MOWING_DIRECTION,
    SERVICE_SET_MOW_HEIGHT,
    SERVICE_SET_RAIN_CONTINUE_TIME,
    SERVICE_SET_RAIN_PERCEPTION,
    SERVICE_SET_VOICE_VOLUME,
    SERVICE_START_FULL_MOW,
    SERVICE_START_OUTER_EDGE_MOW,
    SERVICE_START_DOCK_EDGE_MOW,
    SERVICE_START_ZONE_MOW,
    SERVICE_STOP_MOW,
)
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .commands import async_prepare_cloud_connection, async_start_mowing
from .zones import auto_zones, manual_zones

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
LEGACY_ENTITY_SUFFIXES: tuple[str, ...] = (
    "enable_custom_mowing_direction",
    "custom_mowing_direction_enable",
    "custom_mowing_direction_enabled_button",
    "mow_count",
    "last_service_command_state",
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

    serial_value = service_data.get(ATTR_SERIAL_NUMBER)
    if isinstance(serial_value, str) and serial_value:
        requested_serials.add(serial_value)
    elif isinstance(serial_value, list):
        requested_serials.update(
            item for item in serial_value if isinstance(item, str) and item
        )

    entity_ids = service_data.get("entity_id")
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    if isinstance(entity_ids, list):
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
        return coordinators

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
    async def _handle_start_full_mow(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_start_mowing(coordinator, app_state=1)
            await _async_sync_after_command(coordinator)

    async def _handle_start_outer_edge_mow(service_call) -> None:
        for coordinator in _resolve_target_coordinators(hass, service_call.data):
            await async_start_mowing(
                coordinator,
                app_state=2,
                expected_modes={"bordermowing", "edgemowing", "gototarget"},
            )
            await _async_sync_after_command(coordinator)

    async def _handle_start_dock_edge_mow(service_call) -> None:
        for coordinator in _resolve_target_coordinators(hass, service_call.data):
            if not await async_prepare_cloud_connection(coordinator):
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection; dock mowing was not started"
                )
            await coordinator.client.async_publish_service_command(cmd="nest_mow_start", data=1)
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
            await coordinator.client.async_publish_service_command(
                cmd="stop_all_tasks", data=1
            )
            await _async_sync_after_command(coordinator)

    async def _handle_return_to_dock(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_prepare_cloud_connection(coordinator)
            await coordinator.client.async_publish_service_command(
                cmd="charge_start", data=1
            )
            await _async_sync_after_command(coordinator)

    async def _handle_set_mow_height(service_call) -> None:
        targets = _resolve_target_coordinators(hass, service_call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        mow_height = int(service_call.data[ATTR_MOW_HEIGHT])
        for coordinator in targets:
            await coordinator.client.async_publish_service_command(
                cmd="param_set",
                data={"cutter_height": mow_height, "rid_switch": 0},
            )
            await _async_sync_after_command(coordinator)

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
            if not await async_prepare_cloud_connection(coordinator):
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection; zone mowing was not started"
                )
            await coordinator.client.async_publish_service_command(
                cmd="custom_area_mow_start",
                data={"id": zone_ids},
            )
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
            if not await async_prepare_cloud_connection(coordinator):
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection; auto-zone mowing was not started"
                )
            await coordinator.client.async_publish_service_command(
                cmd="region_mow_start",
                data={"points": points},
            )
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
    if not hass.services.has_service(DOMAIN, SERVICE_RETURN_TO_DOCK):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RETURN_TO_DOCK,
            _handle_return_to_dock,
            schema=base_schema,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SET_MOW_HEIGHT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_MOW_HEIGHT,
            _handle_set_mow_height,
            schema=set_height_schema,
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
        )
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            _LOGGER.warning(
                "Initial refresh failed for %s (%s): %s",
                device.alias,
                device.serial_number,
                coordinator.last_exception,
            )
        await coordinator.async_start_live_shadow()
        coordinators.append(coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Anthbot Genie config entry."""
    coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id, [])
    for coordinator in coordinators:
        await coordinator.async_stop_live_shadow()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            for service_name in (
                SERVICE_START_FULL_MOW,
                SERVICE_START_OUTER_EDGE_MOW,
                SERVICE_START_NO_GO_EDGE_MOW,
                SERVICE_START_DOCK_EDGE_MOW,
                SERVICE_START_ALL_EDGES_MOW,
                SERVICE_STOP_MOW,
                SERVICE_RETURN_TO_DOCK,
                SERVICE_SET_MOW_HEIGHT,
                SERVICE_SET_VOICE_VOLUME,
                SERVICE_SET_CUSTOM_MOWING_DIRECTION,
                SERVICE_CONNECT_CLOUD,
                SERVICE_SET_RAIN_CONTINUE_TIME,
                SERVICE_SET_RAIN_PERCEPTION,
                SERVICE_START_ZONE_MOW,
                SERVICE_START_AUTO_ZONE_MOW,
            ):
                if hass.services.has_service(DOMAIN, service_name):
                    hass.services.async_remove(DOMAIN, service_name)
    return unloaded
