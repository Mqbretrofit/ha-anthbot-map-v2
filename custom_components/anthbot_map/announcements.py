"""Best-effort Anthbot Map announcements for the bundled frontend.

The feed is deliberately isolated from mower control.  It sends only the
integration version, selected display language, mower model names and the
random minimal-presence installation ID.  A failed request always falls back
to the last locally cached response.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import DOMAIN, INTEGRATION_VERSION
from .presence import async_get_presence_installation_id

_LOGGER = logging.getLogger(__name__)

ANNOUNCEMENTS_ENDPOINT = "https://anthbotmap.com/api/anthbot/announcements"
SERVICE_GET_ANNOUNCEMENTS = "announcements_get"
SERVICE_MARK_ANNOUNCEMENTS_READ = "announcements_mark_read"

_SCHEMA = "anthbot-map-announcements-v1"
_STORAGE_VERSION = 1
_STORAGE_KEY = "anthbot_map.announcements"
_RUNTIME_KEY = "_announcements_runtime"
_INTERVAL = timedelta(hours=6)
_MAX_ITEMS = 50
_LANGUAGES = {
    "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "sk",
    "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr", "th", "vi",
    "ko", "km",
}
_CATEGORIES = {"news", "release", "maintenance", "outage", "voice"}
_PRIORITIES = {"normal", "important", "critical"}

_GET_SCHEMA = vol.Schema(
    {
        vol.Optional("language", default="en"): vol.In(_LANGUAGES),
        vol.Optional("refresh", default=False): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)
_MARK_READ_SCHEMA = vol.Schema(
    {
        vol.Required("announcement_ids"): vol.All(
            cv.ensure_list, [vol.All(cv.string, vol.Length(min=1, max=120))]
        ),
        vol.Optional("popup_seen", default=False): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean_item(value: Any) -> dict[str, Any] | None:
    """Return a frontend-safe item or discard malformed server content."""
    if not isinstance(value, dict):
        return None
    announcement_id = value.get("id")
    title = value.get("title")
    body = value.get("body")
    if not isinstance(announcement_id, str) or not 1 <= len(announcement_id) <= 120:
        return None
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
        return None
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= 5000:
        return None
    category = value.get("category", "news")
    priority = value.get("priority", "normal")
    if category not in _CATEGORIES or priority not in _PRIORITIES:
        return None
    link = value.get("link") or value.get("link_url")
    if link is not None and (
        not isinstance(link, str) or not link.startswith("https://") or len(link) > 1000
    ):
        link = None
    return {
        "id": announcement_id,
        "title": title.strip(),
        "body": body.strip(),
        "category": category,
        "priority": priority,
        "show_popup": bool(value.get("show_popup", False)),
        "published_at": value.get("published_at") if isinstance(value.get("published_at"), str) else None,
        "expires_at": value.get("expires_at") if isinstance(value.get("expires_at"), str) else None,
        "link": link,
        "link_label": str(value.get("link_label") or "").strip()[:120] or None,
    }


def _models(hass: HomeAssistant) -> list[str]:
    models: set[str] = set()
    domain_data = hass.data.get(DOMAIN, {})
    if not isinstance(domain_data, dict):
        return []
    for value in domain_data.values():
        if not isinstance(value, list):
            continue
        for coordinator in value:
            model = getattr(getattr(coordinator, "device", None), "model", None)
            if isinstance(model, str) and model.strip():
                models.add(model.strip())
    return sorted(models)


class AnnouncementsRuntime:
    """HA-wide announcement cache and service implementation."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: Store[dict[str, Any]] = Store(
            hass, _STORAGE_VERSION, _STORAGE_KEY
        )
        self.items: list[dict[str, Any]] = []
        self.read_ids: set[str] = set()
        self.popup_seen_ids: set[str] = set()
        self.language = "en"
        self.fetched_at: datetime | None = None
        self.last_error: str | None = None
        self.lock = asyncio.Lock()

    async def async_load(self) -> None:
        data = await self.store.async_load() or {}
        self.items = [
            cleaned
            for item in data.get("items", [])[:_MAX_ITEMS]
            if (cleaned := _clean_item(item)) is not None
        ]
        self.read_ids = {
            value for value in data.get("read_ids", []) if isinstance(value, str)
        }
        self.popup_seen_ids = {
            value
            for value in data.get("popup_seen_ids", [])
            if isinstance(value, str)
        }
        language = data.get("language")
        if language in _LANGUAGES:
            self.language = language
        self.fetched_at = _parse_datetime(data.get("fetched_at"))

    async def async_save(self) -> None:
        active_ids = {item["id"] for item in self.items}
        await self.store.async_save(
            {
                "items": self.items,
                "read_ids": sorted(self.read_ids & active_ids),
                "popup_seen_ids": sorted(self.popup_seen_ids & active_ids),
                "language": self.language,
                "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            }
        )

    def _stale(self) -> bool:
        return self.fetched_at is None or _utcnow() - self.fetched_at >= _INTERVAL

    async def async_refresh(self, language: str) -> None:
        async with self.lock:
            try:
                params = {
                    "version": INTEGRATION_VERSION,
                    "language": language,
                    "installation_id": await async_get_presence_installation_id(
                        self.hass
                    ),
                }
                models = _models(self.hass)
                if models:
                    params["models"] = ",".join(models)
                session = async_get_clientsession(self.hass)
                async with session.get(
                    ANNOUNCEMENTS_ENDPOINT, params=params, timeout=8
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}")
                    payload = await response.json(content_type=None)
                if not isinstance(payload, dict) or payload.get("schema") != _SCHEMA:
                    raise ValueError("unsupported announcement schema")
                raw_items = payload.get("items")
                if not isinstance(raw_items, list):
                    raise ValueError("announcement items are missing")
                self.items = [
                    cleaned
                    for item in raw_items[:_MAX_ITEMS]
                    if (cleaned := _clean_item(item)) is not None
                ]
                self.language = language
                self.fetched_at = _utcnow()
                self.last_error = None
                await self.async_save()
            except Exception as err:  # noqa: BLE001 - never affect mower control
                self.last_error = str(err)[:200]
                _LOGGER.debug("Announcement refresh failed: %s", err)

    def response(self) -> dict[str, Any]:
        active_ids = {item["id"] for item in self.items}
        read_ids = self.read_ids & active_ids
        return {
            "schema": _SCHEMA,
            "items": self.items,
            "read_ids": sorted(read_ids),
            "popup_seen_ids": sorted(self.popup_seen_ids & active_ids),
            "unread_count": len(active_ids - read_ids),
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "stale": self._stale(),
            "available": self.last_error is None or bool(self.items),
        }

    async def async_get(self, language: str, refresh: bool) -> dict[str, Any]:
        if refresh or language != self.language or self._stale():
            await self.async_refresh(language)
        return self.response()

    async def async_mark_read(
        self, announcement_ids: list[str], popup_seen: bool
    ) -> dict[str, Any]:
        active_ids = {item["id"] for item in self.items}
        selected = set(announcement_ids) & active_ids
        self.read_ids.update(selected)
        if popup_seen:
            self.popup_seen_ids.update(selected)
        await self.async_save()
        return self.response()


async def async_register_announcements(hass: HomeAssistant) -> None:
    """Register one HA-wide feed cache and its internal frontend services."""
    domain_data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_RUNTIME_KEY):
        return

    runtime = AnnouncementsRuntime(hass)
    await runtime.async_load()
    domain_data[_RUNTIME_KEY] = runtime

    async def _handle_get(call) -> dict[str, Any]:
        return await runtime.async_get(
            call.data["language"], bool(call.data["refresh"])
        )

    async def _handle_mark_read(call) -> dict[str, Any]:
        return await runtime.async_mark_read(
            call.data["announcement_ids"], bool(call.data["popup_seen"])
        )

    if not hass.services.has_service(DOMAIN, SERVICE_GET_ANNOUNCEMENTS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_ANNOUNCEMENTS,
            _handle_get,
            schema=_GET_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_MARK_ANNOUNCEMENTS_READ):
        hass.services.async_register(
            DOMAIN,
            SERVICE_MARK_ANNOUNCEMENTS_READ,
            _handle_mark_read,
            schema=_MARK_READ_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    async def _scheduled(_now: Any) -> None:
        await runtime.async_refresh(runtime.language)

    domain_data["_announcements_unsubscribe"] = async_track_time_interval(
        hass, _scheduled, _INTERVAL
    )
    hass.async_create_task(runtime.async_refresh(runtime.language))
