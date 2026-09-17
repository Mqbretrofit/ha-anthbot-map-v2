"""Wire HA schedule services and calendar without rewriting __init__.py."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .api import AnthbotGenieApiError
from .const import (
    ATTR_DURATION_HOURS,
    ATTR_ENABLED,
    ATTR_MODE,
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

_LOGGER = logging.getLogger(__name__)
_READY = "ha_schedule_entries"


def _resolve_targets(hass: HomeAssistant, service_data: dict):
    domain_data = hass.data.get(DOMAIN, {})
    coordinators = []
    for key, value in domain_data.items():
        if key in {_READY, "ha_schedule_unsub"}:
            continue
        if isinstance(value, list):
            coordinators.extend(value)
    serial = service_data.get(ATTR_SERIAL_NUMBER)
    requested: set[str] = set()
    if isinstance(serial, str) and serial:
        requested.add(serial)
    elif isinstance(serial, list):
        requested.update(item for item in serial if isinstance(item, str) and item)
    entity_ids = service_data.get("entity_id")
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    if isinstance(entity_ids, list):
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
            vol.Optional(ATTR_SERIAL_NUMBER): vol.Any(cv.string, [cv.string]),
            vol.Optional("entity_id"): vol.Any(cv.entity_id, [cv.entity_id]),
        },
        extra=vol.ALLOW_EXTRA,
    )
    add_schema = vol.Schema(
        {
            vol.Optional(ATTR_SUMMARY, default="HA schedule"): cv.string,
            vol.Optional(ATTR_WEEKDAYS, default="0,1,2,3,4,5,6"): vol.Any(
                cv.string, [cv.string], [int]
            ),
            vol.Required(ATTR_START_TIME): cv.string,
            vol.Optional(ATTR_MODE, default="full"): vol.In(
                ("full", "zone", "auto_zone", "edge", "dock")
            ),
            vol.Optional(ATTR_ZONES): cv.string,
            vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
            vol.Optional("duration_minutes", default=60): vol.All(
                vol.Coerce(int), vol.Range(min=15, max=720)
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
            )

    async def _handle_add(call) -> None:
        targets = _resolve_targets(hass, call.data)
        if not targets:
            raise AnthbotGenieApiError("No target Anthbot mower found")
        for coordinator in targets:
            await async_add_rule(hass, coordinator, dict(call.data))

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


async def async_setup_schedule(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Start the engine, services and calendar platform for one config entry."""
    ready = hass.data.setdefault(DOMAIN, {}).setdefault(_READY, set())
    if entry.entry_id in ready:
        return
    _register_services(hass)
    async_start_schedule_engine(hass)
    await hass.config_entries.async_forward_entry_setups(entry, ["calendar"])
    ready.add(entry.entry_id)

    async def _unload() -> None:
        ready.discard(entry.entry_id)
        try:
            await hass.config_entries.async_forward_entry_unload(entry, "calendar")
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Calendar platform already unloaded for %s", entry.entry_id)

    entry.async_on_unload(_unload)
