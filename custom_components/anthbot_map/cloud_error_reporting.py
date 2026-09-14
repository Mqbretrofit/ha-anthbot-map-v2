"""Opt-in reporting for temporary ANTHBOT cloud/API failures.

Cloud failures are separate from mower firmware errors and from Anthbot Map
parser/control bugs. This observer receives privacy-safe failure signals from
the resilience layer and uploads at most one equivalent report per mower/hour.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVELOPER_INSTALLATION_ID,
    CONF_SEND_AUTOMATIC_DIAGNOSTICS,
    DEVELOPER_DIAGNOSTICS_ENDPOINT,
    DOMAIN,
)
from .developer_reporting import async_send_diagnostics_report
from .firmware_diagnostics import build_firmware_diagnostics_report
from .models.cloud_api_resilience import (
    CloudApiErrorEvent,
    register_cloud_error_listener,
)

_LOGGER = logging.getLogger(__name__)
_REGISTRY_KEY = f"{DOMAIN}_automatic_cloud_error_reporting"
_DEDUPE_SECONDS = 60 * 60


def _entry_option(entry: ConfigEntry, key: str, default: bool = False) -> bool:
    if key in entry.options:
        return bool(entry.options.get(key))
    return bool(entry.data.get(key, default))


def _entry_value(entry: ConfigEntry, key: str) -> Any:
    if key in entry.options:
        return entry.options.get(key)
    return entry.data.get(key)


class _CloudErrorReporter:
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: Any,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._last_scheduled: dict[
            tuple[str, int | None, int | None, str], float
        ] = {}

    def handle_event(self, event: CloudApiErrorEvent) -> None:
        """Schedule one privacy-safe report for a new cloud failure signature."""
        if not _entry_option(self.entry, CONF_SEND_AUTOMATIC_DIAGNOSTICS, False):
            return

        installation_id = _entry_value(self.entry, CONF_DEVELOPER_INSTALLATION_ID)
        if not isinstance(installation_id, str) or not installation_id:
            return

        now = time.monotonic()
        signature = event.signature
        last = self._last_scheduled.get(signature)
        if last is not None and now - last < _DEDUPE_SECONDS:
            return

        # Mark before scheduling so simultaneous retry paths cannot enqueue
        # duplicate uploads for the same mower/cloud failure.
        self._last_scheduled[signature] = now
        cutoff = now - (_DEDUPE_SECONDS * 2)
        stale = [key for key, seen_at in self._last_scheduled.items() if seen_at < cutoff]
        for key in stale:
            self._last_scheduled.pop(key, None)

        self.hass.async_create_task(
            self._async_send_report(installation_id=installation_id, event=event)
        )

    async def _async_send_report(
        self,
        *,
        installation_id: str,
        event: CloudApiErrorEvent,
    ) -> None:
        if not _entry_option(self.entry, CONF_SEND_AUTOMATIC_DIAGNOSTICS, False):
            return

        report = build_firmware_diagnostics_report(
            self.coordinator,
            include_raw_state=False,
            include_identifiers=False,
        )
        report["cloud_api_error"] = {
            "category": "anthbot_cloud",
            "operation": event.operation,
            "api_code": event.api_code,
            "http_status": event.status_code,
            "temporary": event.temporary,
            "attempts": event.attempts,
            "message": event.message,
        }

        session = async_get_clientsession(self.hass)
        sent = await async_send_diagnostics_report(
            session,
            DEVELOPER_DIAGNOSTICS_ENDPOINT,
            installation_id=installation_id,
            report=report,
            trigger="cloud_api_error",
        )
        if not sent:
            _LOGGER.debug(
                "Automatic ANTHBOT cloud error report delivery failed for %s",
                getattr(getattr(self.coordinator, "device", None), "model", None),
            )


async def async_register_cloud_error_reporting(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinators: list[Any],
) -> None:
    """Register one cloud failure observer for every loaded mower."""
    registry: dict[str, list[Callable[[], None]]] = hass.data.setdefault(
        _REGISTRY_KEY, {}
    )
    if entry.entry_id in registry:
        return

    removers: list[Callable[[], None]] = []
    reporters: list[_CloudErrorReporter] = []
    for coordinator in coordinators:
        reporter = _CloudErrorReporter(hass, entry, coordinator)
        reporters.append(reporter)
        serial_number = str(getattr(coordinator.client, "serial_number", "") or "")
        if not serial_number:
            continue
        removers.append(
            register_cloud_error_listener(serial_number, reporter.handle_event)
        )

    registry[entry.entry_id] = removers

    def _cleanup() -> None:
        current = registry.pop(entry.entry_id, [])
        for remove_listener in current:
            try:
                remove_listener()
            except Exception:  # noqa: BLE001 - cleanup must not block unload
                pass

    entry.async_on_unload(_cleanup)
