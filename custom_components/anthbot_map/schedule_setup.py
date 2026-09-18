"""Register ANTHBOT app schedule and Home Assistant override services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .api import AnthbotGenieApiError
from .const import (
    ATTR_DURATION_HOURS,
    ATTR_ENABLED,
    ATTR_MODE,
    ATTR_MOW_HEIGHT,
    ATTR_OVERRIDE_ACTION,
    ATTR_SCHEDULE_ID,
    ATTR_SERIAL_NUMBER,
    ATTR_START_TIME,
    ATTR_SUMMARY,
    ATTR_WEEKDAYS,
    ATTR_ZONES,
    DOMAIN,
    SERVICE_ADD_HA_SCHEDULE,
    SERVICE_DELETE_HA_SCHEDULE,
    SERVICE_OVERRIDE_SCHEDULE,
)
from .schedule_engine import (
    async_add_rule,
    async_apply_override,
    async_delete_rule,
    async_start_schedule_engine,
)

def _resolve_targets(hass: HomeAssistant, service_data: dict):
    domain_data = hass.data.get(DOMAIN, {})
    coordinators = []
    for key, value in domain_data.items():
        if isinstance(value, list):
            coordinators.extend(value)
    serial = service_data.get(ATTR_SERIAL_NUMBER)
    requested: set[str] = set()
    target_requested = False
    if isinstance(serial, str) and serial:
        target_requested = True
        requested.add(serial)
    elif isinstance(serial, list):
        target_requested = bool(serial)
        requested.update(item for item in serial if isinstance(item, str) and item)
    entity_ids = service_data.get("entity_id")
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    if isinstance(entity_ids, list):
        target_requested = target_requested or bool(entity_ids)
        for entity_id in entity_ids:
            state = hass.states.get(entity_id)
            value = state.attributes.get(ATTR_SERIAL_NUMBER) if state else None
            if isinstance(value, str) and value:
                requested.add(value)
    if requested:
        coordinators = [
            item for item in coordinators if item.client.serial_number in requested
        ]
        return coordinators
    return [] if target_requested else coordinators


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_OVERRIDE_SCHEDULE):
        return

    override_schema = vol.Schema(
        {
            vol.Required(ATTR_OVERRIDE_ACTION): vol.In(("mow", "park", "clear")),
            vol.Optional(ATTR_DURATION_HOURS, default=2): vol.All(
                vol.Coerce(float), vol.Range(min=0.25, max=72)
            ),
            vol.Optional(ATTR_MODE, default="full"): vol.In(
                ("full", "zone", "auto_zone", "edge", "dock")
            ),
            vol.Optional(ATTR_ZONES): cv.string,
            vol.Optional(ATTR_MOW_HEIGHT): vol.All(
                vol.Coerce(int), vol.In(list(range(30, 75, 5)))
            ),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    add_schema = vol.Schema(
        {
            vol.Optional(ATTR_SUMMARY, default="ANTHBOT app schedule"): cv.string,
            vol.Optional(ATTR_SCHEDULE_ID): cv.string,
            vol.Optional(ATTR_WEEKDAYS, default="0,1,2,3,4,5,6"): vol.Any(
                cv.string, [cv.string], [int]
            ),
            vol.Required(ATTR_START_TIME): cv.string,
            vol.Optional(ATTR_MODE, default="full"): vol.In(
                ("full", "zone", "auto_zone", "region")
            ),
            vol.Optional(ATTR_ZONES): cv.string,
            vol.Optional(ATTR_MOW_HEIGHT): vol.All(
                vol.Coerce(int), vol.In(list(range(30, 75, 5)))
            ),
            vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
            vol.Optional("duration_minutes", default=60): vol.All(
                vol.Coerce(int), vol.Range(min=15, max=720)
            ),
            vol.Optional("weather_entity"): cv.entity_id,
            vol.Optional("forecast_guard_hours", default=0): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=24)
            ),
            vol.Optional("rain_probability", default=50): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Optional("catch_up_hours", default=0): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=72)
            ),
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    delete_schema = vol.Schema(
        {
            vol.Required(ATTR_SCHEDULE_ID): cv.string,
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )

    async def _handle_override(call) -> None:
        targets = _resolve_targets(hass, call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_apply_override(
                hass,
                coordinator,
                str(call.data[ATTR_OVERRIDE_ACTION]),
                float(call.data.get(ATTR_DURATION_HOURS, 2)),
                str(call.data.get(ATTR_MODE, "full")),
                call.data.get(ATTR_ZONES),
                call.data.get(ATTR_MOW_HEIGHT),
            )

    async def _handle_add(call) -> None:
        targets = _resolve_targets(hass, call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            rule = dict(call.data)
            if ATTR_SCHEDULE_ID in rule:
                rule["id"] = rule[ATTR_SCHEDULE_ID]
            await async_add_rule(hass, coordinator, rule)

    async def _handle_delete(call) -> None:
        targets = _resolve_targets(hass, call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_delete_rule(hass, coordinator, str(call.data[ATTR_SCHEDULE_ID]))

    hass.services.async_register(
        DOMAIN, SERVICE_OVERRIDE_SCHEDULE, _handle_override, schema=override_schema
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_HA_SCHEDULE, _handle_add, schema=add_schema
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_HA_SCHEDULE, _handle_delete, schema=delete_schema
    )


async def async_setup_schedule(hass: HomeAssistant, _entry: ConfigEntry) -> None:
    """Start the shared engine and services before platforms are forwarded."""
    _register_services(hass)
    async_start_schedule_engine(hass)
