"""Minimal ANTHBOT Map installation presence heartbeat.

Only install_id, version and model leave Home Assistant. This is deliberately
separate from the existing detailed developer Reports opt-in.
"""
from __future__ import annotations

from datetime import timedelta
import logging
import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)
_STORAGE_VERSION = 1
_STORAGE_KEY = "anthbot_map.presence"
_ENDPOINT = "https://reports.mqbretrofithungary.online/api/anthbot/presence"
_INTERVAL = timedelta(hours=6)
_RUNTIME_KEY = "_presence_heartbeat_started"


async def _installation_id(hass: HomeAssistant) -> str:
    store: Store[dict[str, str]] = Store(hass, _STORAGE_VERSION, _STORAGE_KEY)
    data = await store.async_load() or {}
    install_id = data.get("install_id")
    try:
        uuid.UUID(str(install_id))
    except (ValueError, TypeError, AttributeError):
        install_id = str(uuid.uuid4())
        await store.async_save({"install_id": install_id})
    return str(install_id)


def _models(hass: HomeAssistant) -> set[str]:
    models: set[str] = set()
    domain_data = hass.data.get("anthbot_map", {})
    if not isinstance(domain_data, dict):
        return models
    for value in domain_data.values():
        if not isinstance(value, list):
            continue
        for coordinator in value:
            device = getattr(coordinator, "device", None)
            model = getattr(device, "model", None)
            if isinstance(model, str) and model.strip():
                models.add(model.strip())
    return models


async def _send(hass: HomeAssistant) -> None:
    models = _models(hass)
    if not models:
        return
    install_id = await _installation_id(hass)
    session = async_get_clientsession(hass)
    for model in sorted(models):
        payload = {
            "install_id": install_id,
            "version": INTEGRATION_VERSION,
            "model": model,
        }
        try:
            async with session.post(_ENDPOINT, json=payload, timeout=8) as response:
                if response.status < 200 or response.status >= 300:
                    _LOGGER.debug("Presence heartbeat returned HTTP %s", response.status)
        except Exception as err:  # noqa: BLE001 - presence must never affect integration
            _LOGGER.debug("Presence heartbeat failed: %s", err)


async def async_start_presence_heartbeat(hass: HomeAssistant) -> None:
    """Start one HA-wide best-effort heartbeat loop."""
    domain_data: dict[str, Any] = hass.data.setdefault("anthbot_map", {})
    if domain_data.get(_RUNTIME_KEY):
        return
    domain_data[_RUNTIME_KEY] = True

    hass.async_create_task(_send(hass))

    async def _scheduled(_now: Any) -> None:
        await _send(hass)

    unsubscribe = async_track_time_interval(hass, _scheduled, _INTERVAL)
    domain_data["_presence_heartbeat_unsubscribe"] = unsubscribe
