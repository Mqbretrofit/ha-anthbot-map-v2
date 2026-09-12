"""Consent UI backend for the optional read-only developer test agent."""

from __future__ import annotations

import secrets
import uuid
from typing import Any

import voluptuous as vol

from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DEVELOPER_AGENT_ENABLED,
    CONF_DEVELOPER_AGENT_KEY,
    CONF_DEVELOPER_INSTALLATION_ID,
    DOMAIN,
    INTEGRATION_VERSION,
)

SERVICE_GET_DEVELOPER_AGENT = "developer_agent_get"
SERVICE_UPDATE_DEVELOPER_AGENT = "developer_agent_update"
CONF_DEVELOPER_AGENT_PROMPT_VERSION = "developer_agent_prompt_version"
_RESOURCE_PATH = "/anthbot-map-v2/developer-agent-optin.js"

_UPDATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVELOPER_AGENT_ENABLED): cv.boolean,
        vol.Optional("dismissed", default=False): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)


def _integration_version() -> str:
    """Return the integration version without blocking file I/O."""
    return INTEGRATION_VERSION


def _first_entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _entry_enabled(entry: ConfigEntry) -> bool:
    if CONF_DEVELOPER_AGENT_ENABLED in entry.options:
        return bool(entry.options.get(CONF_DEVELOPER_AGENT_ENABLED))
    return bool(entry.data.get(CONF_DEVELOPER_AGENT_ENABLED, False))


def _state(hass: HomeAssistant) -> dict[str, Any]:
    entry = _first_entry(hass)
    version = _integration_version()
    if entry is None:
        return {
            "installed": False,
            "integration_version": version,
            "enabled": False,
            "should_show": False,
        }
    enabled = _entry_enabled(entry)
    prompt_version = entry.options.get(
        CONF_DEVELOPER_AGENT_PROMPT_VERSION,
        entry.data.get(CONF_DEVELOPER_AGENT_PROMPT_VERSION),
    )
    return {
        "installed": True,
        "integration_version": version,
        "enabled": enabled,
        "prompt_version": prompt_version,
        "should_show": not enabled and prompt_version != version,
    }


async def _register_resource(hass: HomeAssistant) -> None:
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None or getattr(lovelace, "resource_mode", None) != MODE_STORAGE:
        return
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        return
    await resources.async_get_info()
    url = f"{_RESOURCE_PATH}?v={_integration_version()}"
    matches = [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).split("?", 1)[0] == _RESOURCE_PATH
    ]
    if matches:
        current = matches[0]
        if current.get("url") != url or current.get("type") != "module":
            await resources.async_update_item(
                current["id"],
                {"res_type": "module", "url": url},
            )
        return
    await resources.async_create_item({"res_type": "module", "url": url})


async def async_register_developer_agent_optin(hass: HomeAssistant) -> None:
    """Register read-only developer-agent consent services and frontend."""

    async def _handle_get(_service_call) -> dict[str, Any]:
        return _state(hass)

    async def _handle_update(service_call) -> dict[str, Any]:
        entry = _first_entry(hass)
        if entry is None:
            return _state(hass)

        submitted = CONF_DEVELOPER_AGENT_ENABLED in service_call.data
        requested = bool(
            service_call.data.get(
                CONF_DEVELOPER_AGENT_ENABLED,
                _entry_enabled(entry),
            )
        )
        options = dict(entry.options)
        data = dict(entry.data)
        options[CONF_DEVELOPER_AGENT_PROMPT_VERSION] = _integration_version()

        if submitted:
            options[CONF_DEVELOPER_AGENT_ENABLED] = requested
        if requested:
            installation_id = data.get(CONF_DEVELOPER_INSTALLATION_ID)
            if not isinstance(installation_id, str) or not installation_id:
                installation_id = str(uuid.uuid4())
                data[CONF_DEVELOPER_INSTALLATION_ID] = installation_id
                options[CONF_DEVELOPER_INSTALLATION_ID] = installation_id
            agent_key = data.get(CONF_DEVELOPER_AGENT_KEY)
            if not isinstance(agent_key, str) or len(agent_key) < 32:
                data[CONF_DEVELOPER_AGENT_KEY] = secrets.token_urlsafe(32)

        hass.config_entries.async_update_entry(entry, data=data, options=options)
        return _state(hass)

    if not hass.services.has_service(DOMAIN, SERVICE_GET_DEVELOPER_AGENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_DEVELOPER_AGENT,
            _handle_get,
            schema=vol.Schema({}, extra=vol.PREVENT_EXTRA),
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE_DEVELOPER_AGENT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_DEVELOPER_AGENT,
            _handle_update,
            schema=_UPDATE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    await _register_resource(hass)
