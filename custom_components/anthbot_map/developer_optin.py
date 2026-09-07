"""Optional developer-reporting consent popup backend.

This module is deliberately separate from mower control and Battery Saver.
It registers two internal Home Assistant services used by the bundled frontend
popup and a separate Lovelace resource for the popup code.
"""

from __future__ import annotations

import json
from pathlib import Path
import secrets
import uuid
from typing import Any

import voluptuous as vol

from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AREA_CODE,
    CONF_DEVELOPER_AGENT_ENABLED,
    CONF_DEVELOPER_AGENT_KEY,
    CONF_DEVELOPER_INSTALLATION_ID,
    CONF_SEND_AUTOMATIC_DIAGNOSTICS,
    CONF_SHARE_ANONYMOUS_USAGE,
    DEVELOPER_TELEMETRY_ENDPOINT,
    DOMAIN,
)
from .developer_reporting import async_send_anonymous_usage_report

SERVICE_GET_DEVELOPER_REPORTING = "developer_reporting_get"
SERVICE_UPDATE_DEVELOPER_REPORTING = "developer_reporting_update"
CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED = "developer_opt_in_acknowledged"
CONF_DEVELOPER_PROMPT_VERSION = "developer_prompt_version"

_POPUP_RESOURCE_PATH = "/anthbot-map-v2/developer-optin.js"

_UPDATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SHARE_ANONYMOUS_USAGE): cv.boolean,
        vol.Optional(CONF_SEND_AUTOMATIC_DIAGNOSTICS): cv.boolean,
        vol.Optional(CONF_DEVELOPER_AGENT_ENABLED): cv.boolean,
        vol.Optional("dismissed", default=False): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)


def _integration_version() -> str:
    """Return the currently installed integration version."""
    try:
        manifest = json.loads(
            Path(__file__).with_name("manifest.json").read_text(encoding="utf-8")
        )
        value = manifest.get("version") if isinstance(manifest, dict) else None
    except (OSError, TypeError, ValueError):
        value = None
    return str(value or "unknown")


def _entry_option(entry: Any, key: str, default: bool = False) -> bool:
    """Read an option, preserving legacy config-entry data as fallback."""
    if key in entry.options:
        return bool(entry.options.get(key))
    return bool(entry.data.get(key, default))


def _first_entry(hass: HomeAssistant):
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _preference_state(hass: HomeAssistant) -> dict[str, Any]:
    """Return frontend-safe popup state without account or mower identifiers."""
    entry = _first_entry(hass)
    version = _integration_version()
    if entry is None:
        return {
            "installed": False,
            "integration_version": version,
            "share_anonymous_usage": False,
            "send_automatic_diagnostics": False,
            "developer_agent_enabled": False,
            "acknowledged": False,
            "prompt_version": None,
            "should_show": False,
        }

    acknowledged = bool(
        entry.options.get(
            CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED,
            entry.data.get(CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED, False),
        )
    )
    prompt_version = entry.options.get(
        CONF_DEVELOPER_PROMPT_VERSION,
        entry.data.get(CONF_DEVELOPER_PROMPT_VERSION),
    )
    return {
        "installed": True,
        "integration_version": version,
        "share_anonymous_usage": _entry_option(
            entry, CONF_SHARE_ANONYMOUS_USAGE, False
        ),
        "send_automatic_diagnostics": _entry_option(
            entry, CONF_SEND_AUTOMATIC_DIAGNOSTICS, False
        ),
        "developer_agent_enabled": _entry_option(
            entry, CONF_DEVELOPER_AGENT_ENABLED, False
        ),
        "acknowledged": acknowledged,
        "prompt_version": prompt_version,
        "should_show": not acknowledged and prompt_version != version,
    }


async def _async_register_popup_resource(hass: HomeAssistant) -> None:
    """Register the popup JS as its own cache-busted Lovelace module."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None or getattr(lovelace, "resource_mode", None) != MODE_STORAGE:
        return
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        return

    await resources.async_get_info()
    resource_url = f"{_POPUP_RESOURCE_PATH}?v={_integration_version()}"
    matching = [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).split("?", 1)[0] == _POPUP_RESOURCE_PATH
    ]
    if matching:
        current = matching[0]
        if current.get("url") != resource_url or current.get("type") != "module":
            await resources.async_update_item(
                current["id"],
                {"res_type": "module", "url": resource_url},
            )
        return

    await resources.async_create_item(
        {"res_type": "module", "url": resource_url}
    )


async def async_register_developer_optin(hass: HomeAssistant) -> None:
    """Register the popup resource and its two internal preference services."""

    async def _handle_get(_service_call) -> dict[str, Any]:
        return _preference_state(hass)

    async def _handle_update(service_call) -> dict[str, Any]:
        entry = _first_entry(hass)
        if entry is None:
            return _preference_state(hass)

        old_usage = _entry_option(entry, CONF_SHARE_ANONYMOUS_USAGE, False)
        old_diagnostics = _entry_option(
            entry, CONF_SEND_AUTOMATIC_DIAGNOSTICS, False
        )
        old_agent = _entry_option(entry, CONF_DEVELOPER_AGENT_ENABLED, False)

        usage_was_submitted = CONF_SHARE_ANONYMOUS_USAGE in service_call.data
        diagnostics_was_submitted = (
            CONF_SEND_AUTOMATIC_DIAGNOSTICS in service_call.data
        )
        agent_was_submitted = CONF_DEVELOPER_AGENT_ENABLED in service_call.data

        new_usage = bool(
            service_call.data.get(CONF_SHARE_ANONYMOUS_USAGE, old_usage)
        )
        new_diagnostics = bool(
            service_call.data.get(
                CONF_SEND_AUTOMATIC_DIAGNOSTICS, old_diagnostics
            )
        )
        new_agent = bool(
            service_call.data.get(CONF_DEVELOPER_AGENT_ENABLED, old_agent)
        )

        options = dict(entry.options)
        if usage_was_submitted:
            options[CONF_SHARE_ANONYMOUS_USAGE] = new_usage
        if diagnostics_was_submitted:
            options[CONF_SEND_AUTOMATIC_DIAGNOSTICS] = new_diagnostics
        if agent_was_submitted:
            options[CONF_DEVELOPER_AGENT_ENABLED] = new_agent

        # A dismissal suppresses the popup only for this integration version.
        # Saving at least one enabled checkbox records a permanent acknowledgement;
        # later disabling reporting never makes future update prompts return.
        options[CONF_DEVELOPER_PROMPT_VERSION] = _integration_version()
        acknowledged = bool(
            options.get(
                CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED,
                entry.data.get(CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED, False),
            )
        )
        if (
            (usage_was_submitted and new_usage)
            or (diagnostics_was_submitted and new_diagnostics)
            or (agent_was_submitted and new_agent)
        ):
            acknowledged = True
        if acknowledged:
            options[CONF_DEVELOPER_OPT_IN_ACKNOWLEDGED] = True

        entry_data = dict(entry.data)
        installation_id = options.get(CONF_DEVELOPER_INSTALLATION_ID)
        if not isinstance(installation_id, str) or not installation_id:
            installation_id = entry_data.get(CONF_DEVELOPER_INSTALLATION_ID)
        if (new_usage or new_diagnostics or new_agent) and (
            not isinstance(installation_id, str) or not installation_id
        ):
            installation_id = str(uuid.uuid4())
        if isinstance(installation_id, str) and installation_id:
            # Keep the random ID in data as well because background reporting
            # components read it without exposing account/device identifiers.
            entry_data[CONF_DEVELOPER_INSTALLATION_ID] = installation_id
            options[CONF_DEVELOPER_INSTALLATION_ID] = installation_id

        # The developer-agent key authenticates only this reporting agent. It is
        # unrelated to the ANTHBOT account and is never returned to the frontend.
        if new_agent:
            agent_key = entry_data.get(CONF_DEVELOPER_AGENT_KEY)
            if not isinstance(agent_key, str) or len(agent_key) < 32:
                entry_data[CONF_DEVELOPER_AGENT_KEY] = secrets.token_urlsafe(32)

        hass.config_entries.async_update_entry(
            entry,
            data=entry_data,
            options=options,
        )

        if (
            usage_was_submitted
            and new_usage
            and not old_usage
            and isinstance(installation_id, str)
            and installation_id
        ):
            coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id, [])
            devices = [
                coordinator.device
                for coordinator in coordinators
                if getattr(coordinator, "device", None) is not None
            ]
            if devices:
                session = async_get_clientsession(hass)
                hass.async_create_task(
                    async_send_anonymous_usage_report(
                        session,
                        DEVELOPER_TELEMETRY_ENDPOINT,
                        installation_id=installation_id,
                        area_code=entry.data.get(CONF_AREA_CODE),
                        devices=devices,
                        home_assistant_version=HA_VERSION,
                        event="opt_in",
                    )
                )

        return _preference_state(hass)

    if not hass.services.has_service(DOMAIN, SERVICE_GET_DEVELOPER_REPORTING):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_DEVELOPER_REPORTING,
            _handle_get,
            schema=vol.Schema({}, extra=vol.PREVENT_EXTRA),
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE_DEVELOPER_REPORTING):
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_DEVELOPER_REPORTING,
            _handle_update,
            schema=_UPDATE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    await _async_register_popup_resource(hass)
