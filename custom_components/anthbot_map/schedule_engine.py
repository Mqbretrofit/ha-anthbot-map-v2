"""HA-owned weekly schedule and timed override for Anthbot Map."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_SERIAL_NUMBER,
    CONF_HA_OVERRIDES,
    CONF_HA_SCHEDULES,
    DOMAIN,
    SERVICE_RETURN_TO_DOCK,
    SERVICE_START_AUTO_ZONE_MOW,
    SERVICE_START_DOCK_EDGE_MOW,
    SERVICE_START_FULL_MOW,
    SERVICE_START_OUTER_EDGE_MOW,
    SERVICE_START_ZONE_MOW,
)

_LOGGER = logging.getLogger(__name__)

VALID_MODES = ("full", "zone", "auto_zone", "edge", "dock")
VALID_ACTIONS = ("mow", "park", "clear")
DATA_UNSUB = "ha_schedule_unsub"


def _serial(coordinator) -> str:
    return str(coordinator.client.serial_number)


def _entry_for_coordinator(hass: HomeAssistant, coordinator):
    domain_data = hass.data.get(DOMAIN, {})
    for entry_id, coordinators in domain_data.items():
        if entry_id in {DATA_UNSUB}:
            continue
        if not isinstance(coordinators, list):
            continue
        if coordinator in coordinators:
            return hass.config_entries.async_get_entry(entry_id)
    return None


def schedules_for(coordinator) -> list[dict[str, Any]]:
    entry = _entry_for_coordinator(coordinator.hass, coordinator)
    if entry is None:
        return []
    stored = entry.options.get(CONF_HA_SCHEDULES, {})
    if not isinstance(stored, dict):
        return []
    items = stored.get(_serial(coordinator), [])
    return list(items) if isinstance(items, list) else []


def override_for(coordinator) -> dict[str, Any] | None:
    entry = _entry_for_coordinator(coordinator.hass, coordinator)
    if entry is None:
        return None
    stored = entry.options.get(CONF_HA_OVERRIDES, {})
    if not isinstance(stored, dict):
        return None
    item = stored.get(_serial(coordinator))
    return item if isinstance(item, dict) else None


async def _async_save_maps(
    hass: HomeAssistant,
    coordinator,
    *,
    schedules: list[dict[str, Any]] | None = None,
    override: dict[str, Any] | None | object = ...,
) -> None:
    entry = _entry_for_coordinator(hass, coordinator)
    if entry is None:
        return
    options = dict(entry.options)
    serial = _serial(coordinator)
    if schedules is not None:
        mapping = dict(options.get(CONF_HA_SCHEDULES, {}) or {})
        mapping[serial] = schedules
        options[CONF_HA_SCHEDULES] = mapping
    if override is not ...:
        mapping = dict(options.get(CONF_HA_OVERRIDES, {}) or {})
        if override is None:
            mapping.pop(serial, None)
        else:
            mapping[serial] = override
        options[CONF_HA_OVERRIDES] = mapping
    hass.config_entries.async_update_entry(entry, options=options)


def parse_weekdays(value: Any) -> list[int]:
    if value is None:
        return list(range(7))
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        value = parts
    result: list[int] = []
    names = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    for item in value:
        if isinstance(item, int):
            if 0 <= item <= 6:
                result.append(item)
            continue
        text = str(item).strip().lower()
        if text.isdigit():
            number = int(text)
            if 0 <= number <= 6:
                result.append(number)
        elif text[:3] in names:
            result.append(names[text[:3]])
    return sorted(set(result)) or list(range(7))


def parse_time(value: Any) -> tuple[int, int]:
    text = "07:00" if value in (None, "") else str(value)
    parts = text.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return max(0, min(23, hour)), max(0, min(59, minute))


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    return dt_util.as_local(parsed)


def _as_datetime(value: Any) -> datetime | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return dt_util.as_local(value)
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 10_000_000_000:
            raw /= 1000
        return dt_util.as_local(dt_util.utc_from_timestamp(raw))
    return _parse_iso(value)


def expand_events(coordinator, start: datetime, end: datetime) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    local_start = dt_util.as_local(start)
    local_end = dt_util.as_local(end)
    override = override_for(coordinator)
    if override:
        expires = _parse_iso(override.get("expires"))
        began = _parse_iso(override.get("started")) or (
            expires - timedelta(hours=float(override.get("duration_hours") or 1)) if expires else None
        )
        if expires and began and began < local_end and expires > local_start:
            action = str(override.get("action") or "mow")
            events.append(
                {
                    "uid": f"override-{_serial(coordinator)}",
                    "summary": f"Override: {action}",
                    "start": began,
                    "end": expires,
                    "description": action,
                }
            )
    cursor = local_start.date()
    last = local_end.date()
    while cursor <= last:
        weekday = cursor.weekday()
        for rule in schedules_for(coordinator):
            if not rule.get("enabled", True):
                continue
            if weekday not in parse_weekdays(rule.get("weekdays")):
                continue
            hour, minute = parse_time(rule.get("start_time"))
            begins = dt_util.as_local(datetime.combine(cursor, datetime.min.time())).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            duration = int(rule.get("duration_minutes") or 60)
            finishes = begins + timedelta(minutes=max(15, duration))
            if finishes <= local_start or begins >= local_end:
                continue
            events.append(
                {
                    "uid": str(rule.get("id") or uuid.uuid4()),
                    "summary": str(rule.get("summary") or rule.get("mode") or "Mow"),
                    "start": begins,
                    "end": finishes,
                    "description": str(rule.get("mode") or "full"),
                }
            )
        appointment = coordinator.reported_state.get("appointment_time")
        stamp = _as_datetime(appointment)
        if stamp and cursor == dt_util.as_local(stamp).date():
            local_stamp = dt_util.as_local(stamp)
            if local_start <= local_stamp < local_end:
                events.append(
                    {
                        "uid": f"app-{_serial(coordinator)}-{local_stamp.date()}",
                        "summary": "Anthbot appointment",
                        "start": local_stamp,
                        "end": local_stamp + timedelta(hours=1),
                        "description": "cloud",
                    }
                )
        cursor += timedelta(days=1)
    events.sort(key=lambda item: item["start"])
    return events


def _mower_busy(coordinator) -> bool:
    status = coordinator.reported_state.get("robot_sta")
    if isinstance(status, dict):
        status = status.get("value")
    text = str(status or "").lower()
    return any(token in text for token in ("mow", "run", "work", "cut"))


async def _async_run_mode(hass: HomeAssistant, coordinator, mode: str, zones: str | None) -> None:
    serial = _serial(coordinator)
    data = {ATTR_SERIAL_NUMBER: serial}
    if mode == "edge":
        await hass.services.async_call(DOMAIN, SERVICE_START_OUTER_EDGE_MOW, data, blocking=True)
    elif mode == "dock":
        await hass.services.async_call(DOMAIN, SERVICE_START_DOCK_EDGE_MOW, data, blocking=True)
    elif mode == "auto_zone":
        data["auto_zones"] = zones or ""
        await hass.services.async_call(DOMAIN, SERVICE_START_AUTO_ZONE_MOW, data, blocking=True)
    elif mode == "zone":
        data["zones"] = zones or ""
        await hass.services.async_call(DOMAIN, SERVICE_START_ZONE_MOW, data, blocking=True)
    else:
        await hass.services.async_call(DOMAIN, SERVICE_START_FULL_MOW, data, blocking=True)


async def async_apply_override(
    hass: HomeAssistant,
    coordinator,
    action: str,
    duration_hours: float,
    mode: str = "full",
    zones: str | None = None,
) -> dict[str, Any] | None:
    action = action.strip().lower()
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unsupported override action: {action}")
    if action == "clear":
        await _async_save_maps(hass, coordinator, override=None)
        return None
    now = dt_util.now()
    hours = max(0.25, float(duration_hours))
    payload = {
        "action": action,
        "mode": mode if mode in VALID_MODES else "full",
        "zones": zones,
        "started": now.isoformat(),
        "expires": (now + timedelta(hours=hours)).isoformat(),
        "duration_hours": hours,
        "fired": False,
    }
    await _async_save_maps(hass, coordinator, override=payload)
    if action == "park":
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RETURN_TO_DOCK,
            {ATTR_SERIAL_NUMBER: _serial(coordinator)},
            blocking=True,
        )
        payload["fired"] = True
    elif action == "mow":
        await _async_run_mode(hass, coordinator, payload["mode"], zones)
        payload["fired"] = True
    await _async_save_maps(hass, coordinator, override=payload)
    return payload


async def async_add_rule(hass: HomeAssistant, coordinator, rule: dict[str, Any]) -> dict[str, Any]:
    item = {
        "id": str(rule.get("id") or uuid.uuid4()),
        "summary": str(rule.get("summary") or "HA schedule"),
        "weekdays": parse_weekdays(rule.get("weekdays")),
        "start_time": "{:02d}:{:02d}".format(*parse_time(rule.get("start_time"))),
        "mode": rule.get("mode") if rule.get("mode") in VALID_MODES else "full",
        "zones": rule.get("zones") or None,
        "enabled": bool(rule.get("enabled", True)),
        "duration_minutes": int(rule.get("duration_minutes") or 60),
    }
    items = [existing for existing in schedules_for(coordinator) if existing.get("id") != item["id"]]
    items.append(item)
    await _async_save_maps(hass, coordinator, schedules=items)
    return item


async def async_delete_rule(hass: HomeAssistant, coordinator, schedule_id: str) -> None:
    items = [item for item in schedules_for(coordinator) if str(item.get("id")) != str(schedule_id)]
    await _async_save_maps(hass, coordinator, schedules=items)


async def async_tick(hass: HomeAssistant, coordinator, now: datetime | None = None) -> None:
    current = dt_util.as_local(now or dt_util.now())
    override = override_for(coordinator)
    if override:
        expires = _parse_iso(override.get("expires"))
        if expires and current >= expires:
            await _async_save_maps(hass, coordinator, override=None)
            _LOGGER.info("Anthbot override expired for %s", _serial(coordinator))
            return
        if override.get("action") == "park":
            return
        if override.get("action") == "mow" and not override.get("fired"):
            await _async_run_mode(
                hass, coordinator, str(override.get("mode") or "full"), override.get("zones")
            )
            override["fired"] = True
            await _async_save_maps(hass, coordinator, override=override)
        return
    if _mower_busy(coordinator):
        return
    for rule in schedules_for(coordinator):
        if not rule.get("enabled", True):
            continue
        if current.weekday() not in parse_weekdays(rule.get("weekdays")):
            continue
        hour, minute = parse_time(rule.get("start_time"))
        if current.hour != hour or current.minute != minute:
            continue
        last = coordinator.reported_state.get("_ha_schedule_last_fire")
        stamp = f"{current.date()} {hour:02d}:{minute:02d} {rule.get('id')}"
        if last == stamp:
            continue
        state = dict(coordinator.reported_state)
        state["_ha_schedule_last_fire"] = stamp
        coordinator.async_set_updated_data(state)
        await _async_run_mode(hass, coordinator, str(rule.get("mode") or "full"), rule.get("zones"))
        return


@callback
def async_start_schedule_engine(hass: HomeAssistant) -> None:
    if hass.data.setdefault(DOMAIN, {}).get(DATA_UNSUB):
        return

    async def _interval(_now) -> None:
        domain_data = hass.data.get(DOMAIN, {})
        for entry_id, coordinators in list(domain_data.items()):
            if entry_id == DATA_UNSUB or not isinstance(coordinators, list):
                continue
            for coordinator in coordinators:
                try:
                    await async_tick(hass, coordinator)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception(
                        "HA schedule tick failed for %s",
                        getattr(getattr(coordinator, "client", None), "serial_number", "?"),
                    )

    hass.data[DOMAIN][DATA_UNSUB] = async_track_time_interval(
        hass, _interval, timedelta(seconds=30)
    )


async def async_stop_schedule_engine(hass: HomeAssistant) -> None:
    unsub = hass.data.get(DOMAIN, {}).pop(DATA_UNSUB, None)
    if unsub:
        unsub()
