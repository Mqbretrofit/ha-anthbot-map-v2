"""Automatic opt-in diagnostics for active mower errors and task-event errors.

This module is deliberately isolated from mower control.  It only observes the
already published coordinator state and, when the user enabled automatic
diagnostics, sends one privacy-filtered manufacturer report per error episode.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVELOPER_INSTALLATION_ID,
    CONF_SEND_AUTOMATIC_DIAGNOSTICS,
    DEVELOPER_DIAGNOSTICS_ENDPOINT,
    DOMAIN,
    ERROR_CODE_DESCRIPTIONS,
)
from .developer_reporting import async_send_diagnostics_report
from .firmware_diagnostics import build_firmware_diagnostics_report

_LOGGER = logging.getLogger(__name__)
_REGISTRY_KEY = f"{DOMAIN}_automatic_robot_error_reporting"


def _entry_option(entry: ConfigEntry, key: str, default: bool = False) -> bool:
    if key in entry.options:
        return bool(entry.options.get(key))
    return bool(entry.data.get(key, default))


def _entry_value(entry: ConfigEntry, key: str) -> Any:
    if key in entry.options:
        return entry.options.get(key)
    return entry.data.get(key)


def _unwrap(value: Any) -> Any:
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def _error_code(state: dict[str, Any]) -> int | None:
    value = _unwrap(state.get("err_code"))
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    return code if code != 0 else None


def _task_event_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    payload = state.get("_task_events")
    if isinstance(payload, dict):
        payload = payload.get("data")
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _event_sort_key(event: dict[str, Any]) -> tuple[int, str]:
    raw = event.get("create_time", event.get("time", event.get("timestamp")))
    try:
        return (1, f"{int(raw):020d}")
    except (TypeError, ValueError):
        return (0, str(raw or ""))


def _latest_task_event(state: dict[str, Any]) -> dict[str, Any] | None:
    items = _task_event_items(state)
    return max(items, key=_event_sort_key) if items else None


def _is_error_event(event: dict[str, Any] | None) -> bool:
    if not isinstance(event, dict):
        return False
    return str(event.get("code_type") or "").strip().casefold() == "error"


def _event_signature(event: dict[str, Any] | None) -> tuple[str, str, str] | None:
    if not isinstance(event, dict):
        return None
    return (
        str(event.get("id") or ""),
        str(event.get("code") or ""),
        str(event.get("create_time", event.get("time", event.get("timestamp"))) or ""),
    )


def _state_value(state: dict[str, Any], key: str) -> Any:
    return _unwrap(state.get(key))


class _RobotErrorReporter:
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: Any,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.active_error_code: int | None = None
        self.last_error_event_signature: tuple[str, str, str] | None = None

        state = getattr(coordinator, "reported_state", None)
        if not isinstance(state, dict):
            state = {}
        # Do not replay an old historical task-event error on every HA restart
        # when the mower currently has no active err_code.  Active errors are
        # intentionally handled immediately after registration below.
        if _error_code(state) is None:
            event = _latest_task_event(state)
            if _is_error_event(event):
                self.last_error_event_signature = _event_signature(event)

    def handle_update(self) -> None:
        if not _entry_option(self.entry, CONF_SEND_AUTOMATIC_DIAGNOSTICS, False):
            return

        installation_id = _entry_value(self.entry, CONF_DEVELOPER_INSTALLATION_ID)
        if not isinstance(installation_id, str) or not installation_id:
            return

        state = getattr(self.coordinator, "reported_state", None)
        if not isinstance(state, dict):
            return

        code = _error_code(state)
        if code is None:
            self.active_error_code = None
        code_is_new = code is not None and code != self.active_error_code

        event = _latest_task_event(state)
        event_signature = _event_signature(event) if _is_error_event(event) else None
        event_is_new = (
            event_signature is not None
            and event_signature != self.last_error_event_signature
        )

        if not code_is_new and not event_is_new:
            return

        # Mark before scheduling so several live-shadow updates for the same
        # incident cannot enqueue duplicate uploads.
        if code is not None:
            self.active_error_code = code
        if event_signature is not None:
            self.last_error_event_signature = event_signature

        trigger = "mower_error_code" if code_is_new else "task_event_error"
        self.hass.async_create_task(
            self._async_send_report(
                installation_id=installation_id,
                trigger=trigger,
                error_code=code,
                event=event if isinstance(event, dict) else None,
            )
        )

    async def _async_send_report(
        self,
        *,
        installation_id: str,
        trigger: str,
        error_code: int | None,
        event: dict[str, Any] | None,
    ) -> None:
        state = getattr(self.coordinator, "reported_state", None)
        if not isinstance(state, dict):
            state = {}

        report = build_firmware_diagnostics_report(
            self.coordinator,
            include_raw_state=False,
            include_identifiers=False,
        )
        report["diagnostic_event"] = {
            "trigger": trigger,
            "err_code": error_code,
            "err_description": (
                ERROR_CODE_DESCRIPTIONS.get(error_code)
                if isinstance(error_code, int)
                else None
            ),
            "event_code": _state_value(state, "event_code"),
            "cloud_task_event_code": _state_value(state, "cloud_task_event_code"),
            "mode": _state_value(state, "mode"),
            "robot_sta": _state_value(state, "robot_sta"),
            "online": _state_value(state, "online"),
            "task_event": event,
        }

        session = async_get_clientsession(self.hass)
        sent = await async_send_diagnostics_report(
            session,
            DEVELOPER_DIAGNOSTICS_ENDPOINT,
            installation_id=installation_id,
            report=report,
            trigger=trigger,
        )
        if not sent:
            _LOGGER.debug(
                "Automatic robot error report delivery failed for %s",
                getattr(getattr(self.coordinator, "device", None), "model", None),
            )


async def async_register_robot_error_reporting(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinators: list[Any],
) -> None:
    """Register one deduplicating error observer for every loaded mower."""
    registry: dict[str, list[Callable[[], None]]] = hass.data.setdefault(
        _REGISTRY_KEY, {}
    )
    if entry.entry_id in registry:
        return

    removers: list[Callable[[], None]] = []
    reporters: list[_RobotErrorReporter] = []
    for coordinator in coordinators:
        reporter = _RobotErrorReporter(hass, entry, coordinator)
        reporters.append(reporter)
        removers.append(coordinator.async_add_listener(reporter.handle_update))

    registry[entry.entry_id] = removers

    def _cleanup() -> None:
        current = registry.pop(entry.entry_id, [])
        for remove_listener in current:
            try:
                remove_listener()
            except Exception:  # noqa: BLE001 - cleanup must not block unload
                pass

    entry.async_on_unload(_cleanup)

    # Capture a mower that is already in an active error state when Home
    # Assistant starts or the integration is reloaded.
    for reporter in reporters:
        reporter.handle_update()
