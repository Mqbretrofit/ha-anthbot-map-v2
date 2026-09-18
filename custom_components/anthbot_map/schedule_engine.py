"""ANTHBOT app schedule mirror plus Home Assistant override/weather layer."""

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
    ATTR_MOW_HEIGHT,
    CONF_HA_OVERRIDES,
    CONF_HA_SCHEDULES,
    DOMAIN,
    SERVICE_RETURN_TO_DOCK,
    SERVICE_START_AUTO_ZONE_MOW,
    SERVICE_START_DOCK_EDGE_MOW,
    SERVICE_START_FULL_MOW,
    SERVICE_START_OUTER_EDGE_MOW,
    SERVICE_START_ZONE_MOW,
    SERVICE_SET_MOW_HEIGHT,
)
from .mower_status import mower_activity_name
from .native_schedule import (
    async_publish_native_plan_change,
    async_refresh_native_plan,
    build_native_entry,
    find_native_entry,
    native_plan_for,
    native_rules_for,
)

_LOGGER = logging.getLogger(__name__)

VALID_MODES = ("full", "zone", "auto_zone", "edge", "dock")
VALID_ACTIONS = ("mow", "park", "clear")
DATA_UNSUB = f"{DOMAIN}_schedule_unsub"

EVENT_SCHEDULE_TRIGGERED = f"{DOMAIN}_schedule_triggered"
EVENT_SCHEDULE_SKIPPED = f"{DOMAIN}_schedule_skipped"
EVENT_SCHEDULE_ERROR = f"{DOMAIN}_schedule_error"
EVENT_OVERRIDE_CHANGED = f"{DOMAIN}_override_changed"

RAINY_CONDITIONS = {
    "hail",
    "lightning-rainy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
}


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
    """Return the native app schedules with HA-only presentation metadata."""
    entry = _entry_for_coordinator(coordinator.hass, coordinator)
    stored = entry.options.get(CONF_HA_SCHEDULES, {}) if entry is not None else {}
    if not isinstance(stored, dict):
        stored = {}
    items = stored.get(_serial(coordinator), [])
    metadata = list(items) if isinstance(items, list) else []
    return native_rules_for(coordinator, metadata)


def override_for(coordinator) -> dict[str, Any] | None:
    entry = _entry_for_coordinator(coordinator.hass, coordinator)
    if entry is None:
        return None
    stored = entry.options.get(CONF_HA_OVERRIDES, {})
    if not isinstance(stored, dict):
        return None
    item = stored.get(_serial(coordinator))
    return item if isinstance(item, dict) else None


def _schedule_metadata(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist only HA-only annotations; native appointment data stays cloud-owned."""
    keys = (
        "id",
        "summary",
        "duration_minutes",
        "weather_entity",
        "forecast_guard_hours",
        "rain_probability",
        "catch_up_hours",
        "pending_catch_up",
        "last_fired",
    )
    return [
        {key: item.get(key) for key in keys if key in item}
        for item in items
        if isinstance(item, dict) and item.get("id") not in (None, "")
    ]


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
        mapping[serial] = _schedule_metadata(schedules)
        options[CONF_HA_SCHEDULES] = mapping
    if override is not ...:
        mapping = dict(options.get(CONF_HA_OVERRIDES, {}) or {})
        if override is None:
            mapping.pop(serial, None)
        else:
            mapping[serial] = override
        options[CONF_HA_OVERRIDES] = mapping
    hass.config_entries.async_update_entry(entry, options=options)
    # Calendar and next-mow entities share the mower coordinator. Schedule
    # changes are rare, so one semantic refresh here keeps them immediately
    # accurate without adding a polling loop or touching cloud state.
    coordinator.async_set_updated_data(dict(coordinator.reported_state))


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
    return sorted(set(result))


def parse_time(value: Any) -> tuple[int, int]:
    text = "07:00" if value in (None, "") else str(value)
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("start_time must use HH:MM format")
    hour = int(parts[0])
    minute = int(parts[1])
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("start_time must be a valid local time")
    return hour, minute


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
                    "source": "override",
                    "mode": str(override.get("mode") or "full"),
                    "zones": override.get("zones"),
                    "mow_height": override.get("mow_height"),
                }
            )
    cursor = local_start.date()
    last = local_end.date()
    while cursor <= last:
        weekday = cursor.weekday()
        for rule in schedules_for(coordinator):
            if not rule.get("enabled", True):
                continue
            if rule.get("repeating", True) is False:
                begins = _as_datetime(rule.get("start_datetime"))
                if begins is None or begins.date() != cursor:
                    continue
            else:
                if weekday not in parse_weekdays(rule.get("weekdays")):
                    continue
                hour, minute = parse_time(rule.get("start_time"))
                begins = datetime.combine(
                    cursor,
                    datetime.min.time().replace(hour=hour, minute=minute),
                    tzinfo=dt_util.get_default_time_zone(),
                )
            duration = int(rule.get("duration_minutes") or 60)
            finishes = begins + timedelta(minutes=max(15, duration))
            if finishes <= local_start or begins >= local_end:
                continue
            details = [f"mode={str(rule.get('mode') or 'full')}"]
            if rule.get("zones"):
                details.append(f"zones={rule['zones']}")
            if rule.get("mow_height") is not None:
                details.append(f"height={rule['mow_height']}")
            if rule.get("weather_entity"):
                details.append(f"weather={rule['weather_entity']}")
            events.append(
                {
                    "uid": str(rule.get("id") or uuid.uuid4()),
                    "summary": str(rule.get("summary") or rule.get("mode") or "Mow"),
                    "start": begins,
                    "end": finishes,
                    "description": "; ".join(details),
                    "source": "anthbot_app",
                    "mode": str(rule.get("mode") or "full"),
                    "zones": rule.get("zones"),
                    "mow_height": rule.get("mow_height"),
                    "weather_entity": rule.get("weather_entity"),
                    "last_fired": rule.get("last_fired"),
                }
            )
        cursor += timedelta(days=1)
    events.sort(key=lambda item: item["start"])
    return events


def next_mow_event(
    coordinator: Any, now: datetime | None = None
) -> dict[str, Any] | None:
    """Return the next truthful mowing event after applying HA override rules."""
    current = dt_util.as_local(now or dt_util.now())
    search_start = current
    override = override_for(coordinator)
    if override:
        expires = _parse_iso(override.get("expires"))
        action = str(override.get("action") or "")
        if expires and expires > current:
            if action == "mow":
                started = _parse_iso(override.get("started")) or current
                return {
                    "uid": f"override-{_serial(coordinator)}",
                    "summary": "Override: mow",
                    "start": started,
                    "end": expires,
                    "description": "mow",
                    "source": "override",
                    "mode": str(override.get("mode") or "full"),
                    "zones": override.get("zones"),
                    "mow_height": override.get("mow_height"),
                }
            if action == "park":
                search_start = expires

    events = expand_events(
        coordinator,
        search_start,
        search_start + timedelta(days=8),
    )
    for item in events:
        if item.get("source") == "override":
            continue
        if item["start"] >= search_start:
            return item
        if item.get("source") == "anthbot_app":
            began = item["start"]
            same_minute = began.replace(second=0, microsecond=0) == search_start.replace(
                second=0, microsecond=0
            )
            stamp = (
                f"{began.date()} {began.hour:02d}:{began.minute:02d} "
                f"{item.get('uid')}"
            )
            if same_minute and item.get("last_fired") != stamp:
                return item
    return None


def _mower_busy(coordinator) -> bool:
    activity = mower_activity_name(coordinator.reported_state)
    if activity in {"mowing", "returning", "error"}:
        return True
    status = coordinator.reported_state.get("robot_sta")
    if isinstance(status, dict):
        status = status.get("value")
    text = str(status or "").lower()
    return any(token in text for token in ("mow", "run", "work", "cut"))


def pending_catch_up(coordinator: Any) -> dict[str, Any] | None:
    """Return the earliest weather-delayed schedule, if one exists."""
    pending = [
        (rule, rule.get("pending_catch_up"))
        for rule in schedules_for(coordinator)
        if isinstance(rule.get("pending_catch_up"), dict)
    ]
    if not pending:
        return None
    pending.sort(
        key=lambda item: str(item[1].get("scheduled_for") or "")
    )
    rule, details = pending[0]
    return {
        **details,
        "schedule_id": str(rule.get("id") or ""),
        "summary": str(rule.get("summary") or "ANTHBOT app schedule"),
        "mode": str(rule.get("mode") or "full"),
        "zones": rule.get("zones"),
        "mow_height": rule.get("mow_height"),
    }


def _forecast_items(response: Any, entity_id: str) -> list[dict[str, Any]]:
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if not isinstance(response, dict):
        return []
    payload = response.get(entity_id, response)
    if isinstance(payload, dict):
        payload = payload.get("forecast")
    return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []


async def _async_weather_block_reason(
    hass: HomeAssistant,
    rule: dict[str, Any],
    current: datetime,
) -> str | None:
    """Return a reason when current conditions or forecast should delay mowing."""
    entity_id = str(rule.get("weather_entity") or "").strip()
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or str(state.state).lower() in {"unknown", "unavailable"}:
        return "weather_unavailable"
    condition = str(state.state).strip().lower()
    if condition in RAINY_CONDITIONS:
        return f"weather_{condition}"

    guard_hours = float(rule.get("forecast_guard_hours") or 0)
    if guard_hours <= 0:
        return None
    forecast = _forecast_items(state.attributes.get("forecast"), entity_id)
    if not forecast and hass.services.has_service("weather", "get_forecasts"):
        try:
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": entity_id, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
            forecast = _forecast_items(response, entity_id)
        except Exception as err:  # Weather providers are optional dependencies.
            _LOGGER.debug("Unable to read forecast from %s: %s", entity_id, err)

    cutoff = current + timedelta(hours=guard_hours)
    probability_limit = float(rule.get("rain_probability") or 50)
    for item in forecast:
        forecast_time = _parse_iso(item.get("datetime"))
        if forecast_time and (forecast_time < current or forecast_time > cutoff):
            continue
        forecast_condition = str(item.get("condition") or "").strip().lower()
        if forecast_condition in RAINY_CONDITIONS:
            return f"forecast_{forecast_condition}"
        try:
            probability = float(item.get("precipitation_probability") or 0)
        except (TypeError, ValueError):
            probability = 0
        if probability >= probability_limit:
            return f"forecast_rain_probability_{probability:g}"
    return None


async def _async_run_mode(
    hass: HomeAssistant,
    coordinator,
    mode: str,
    zones: str | None,
    mow_height: int | None = None,
) -> None:
    serial = _serial(coordinator)
    data = {ATTR_SERIAL_NUMBER: serial}
    if mow_height is not None:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MOW_HEIGHT,
            {ATTR_SERIAL_NUMBER: serial, ATTR_MOW_HEIGHT: mow_height},
            blocking=True,
        )
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
    mow_height: int | None = None,
) -> dict[str, Any] | None:
    action = action.strip().lower()
    if action not in VALID_ACTIONS:
        raise ValueError(f"Unsupported override action: {action}")
    if action == "clear":
        await _async_save_maps(hass, coordinator, override=None)
        hass.bus.async_fire(
            EVENT_OVERRIDE_CHANGED,
            {"serial_number": _serial(coordinator), "action": "clear"},
        )
        return None
    now = dt_util.now()
    hours = max(0.25, float(duration_hours))
    payload = {
        "action": action,
        "mode": mode if mode in VALID_MODES else "full",
        "zones": zones,
        "mow_height": mow_height,
        "started": now.isoformat(),
        "expires": (now + timedelta(hours=hours)).isoformat(),
        "duration_hours": hours,
        "fired": True,
    }
    await _async_save_maps(hass, coordinator, override=payload)
    hass.bus.async_fire(
        EVENT_OVERRIDE_CHANGED,
        {
            "serial_number": _serial(coordinator),
            "action": action,
            "expires": payload["expires"],
            "mode": payload["mode"],
            "zones": zones,
            "mow_height": mow_height,
        },
    )
    try:
        if action == "park":
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RETURN_TO_DOCK,
                {ATTR_SERIAL_NUMBER: _serial(coordinator)},
                blocking=True,
            )
        elif action == "mow":
            await _async_run_mode(
                hass, coordinator, payload["mode"], zones, mow_height
            )
    except Exception as err:
        # Do not leave an active override behind when its initiating command
        # was rejected. That would suppress schedules while doing no work.
        await _async_save_maps(hass, coordinator, override=None)
        hass.bus.async_fire(
            EVENT_SCHEDULE_ERROR,
            {
                "serial_number": _serial(coordinator),
                "schedule_id": "override",
                "summary": f"Override: {action}",
                "error": f"{type(err).__name__}: {err}",
            },
        )
        raise
    return payload


async def async_add_rule(hass: HomeAssistant, coordinator, rule: dict[str, Any]) -> dict[str, Any]:
    requested_id = str(rule.get("id") or "")
    current_rules = schedules_for(coordinator)
    previous = next(
        (
            existing
            for existing in current_rules
            if str(existing.get("id")) == requested_id
        ),
        None,
    )
    plan = native_plan_for(coordinator)
    found = find_native_entry(plan, requested_id) if requested_id else None
    previous_raw = found[1] if found is not None else None
    native_entry = build_native_entry(coordinator, rule, previous_raw)
    if (
        previous_raw is None
        and plan.get("version") not in (None, "", 0)
        and native_entry.get("id") in (None, "")
    ):
        numeric_ids: list[int] = []
        for existing in plan.get("value", []):
            if not isinstance(existing, dict):
                continue
            try:
                numeric_ids.append(int(existing.get("id")))
            except (TypeError, ValueError):
                continue
        native_entry["id"] = max(numeric_ids, default=0) + 1

    target_index = found[0] if found is not None else len(plan.get("value", []))
    await async_publish_native_plan_change(
        coordinator,
        operation="edit" if found is not None else "add",
        schedule_id=requested_id or None,
        entry=native_entry,
    )
    refreshed = native_rules_for(coordinator)
    native_rule = next(
        (item for item in refreshed if item.get("_native_index") == target_index),
        refreshed[-1] if refreshed else None,
    )
    if native_rule is None:
        raise ValueError("The native ANTHBOT schedule could not be mirrored")
    schedule_id = str(native_rule["id"])
    metadata = {
        "id": schedule_id,
        "summary": str(rule.get("summary") or "ANTHBOT app schedule"),
        "duration_minutes": int(rule.get("duration_minutes") or 60),
        "weather_entity": rule.get("weather_entity") or None,
        "forecast_guard_hours": float(rule.get("forecast_guard_hours") or 0),
        "rain_probability": int(rule.get("rain_probability") or 50),
        "catch_up_hours": float(rule.get("catch_up_hours") or 0),
        "pending_catch_up": previous.get("pending_catch_up") if previous else None,
        # Updating a rule during its active minute must not make it eligible
        # for a second start command.
        "last_fired": previous.get("last_fired") if previous else None,
    }
    entry = _entry_for_coordinator(hass, coordinator)
    stored = entry.options.get(CONF_HA_SCHEDULES, {}) if entry is not None else {}
    old_items = stored.get(_serial(coordinator), []) if isinstance(stored, dict) else []
    items = [
        existing
        for existing in old_items
        if isinstance(existing, dict)
        and str(existing.get("id")) not in {schedule_id, requested_id}
    ]
    items.append(metadata)
    await _async_save_maps(hass, coordinator, schedules=items)
    return next(
        (item for item in schedules_for(coordinator) if str(item.get("id")) == schedule_id),
        native_rule,
    )


async def async_delete_rule(hass: HomeAssistant, coordinator, schedule_id: str) -> None:
    await async_publish_native_plan_change(
        coordinator,
        operation="delete",
        schedule_id=str(schedule_id),
    )
    entry = _entry_for_coordinator(hass, coordinator)
    stored = entry.options.get(CONF_HA_SCHEDULES, {}) if entry is not None else {}
    old_items = stored.get(_serial(coordinator), []) if isinstance(stored, dict) else []
    items = [
        item
        for item in old_items
        if isinstance(item, dict) and str(item.get("id")) != str(schedule_id)
    ]
    await _async_save_maps(hass, coordinator, schedules=items)


def _due_rules(
    coordinator: Any, current: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rules = schedules_for(coordinator)
    due: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        if rule.get("repeating", True) is False:
            scheduled = _as_datetime(rule.get("start_datetime"))
            if scheduled is None or scheduled.replace(second=0, microsecond=0) != current.replace(
                second=0, microsecond=0
            ):
                continue
            hour, minute = scheduled.hour, scheduled.minute
        else:
            if current.weekday() not in parse_weekdays(rule.get("weekdays")):
                continue
            hour, minute = parse_time(rule.get("start_time"))
            if current.hour != hour or current.minute != minute:
                continue
        stamp = f"{current.date()} {hour:02d}:{minute:02d} {rule.get('id')}"
        if rule.get("last_fired") == stamp:
            continue
        due.append(rule)
    return rules, due


async def _async_mark_skipped(
    hass: HomeAssistant,
    coordinator: Any,
    current: datetime,
    rules: list[dict[str, Any]],
    due: list[dict[str, Any]],
    reason: str,
) -> None:
    for rule in due:
        hour, minute = parse_time(rule.get("start_time"))
        rule["last_fired"] = (
            f"{current.date()} {hour:02d}:{minute:02d} {rule.get('id')}"
        )
        hass.bus.async_fire(
            EVENT_SCHEDULE_SKIPPED,
            {
                "serial_number": _serial(coordinator),
                "schedule_id": str(rule.get("id") or ""),
                "summary": str(rule.get("summary") or "ANTHBOT app schedule"),
                "reason": reason,
                "scheduled_for": current.isoformat(),
                "mode": str(rule.get("mode") or "full"),
                "zones": rule.get("zones"),
                "mow_height": rule.get("mow_height"),
            },
        )
    if due:
        await _async_save_maps(hass, coordinator, schedules=rules)


async def _async_process_catch_up(
    hass: HomeAssistant,
    coordinator: Any,
    current: datetime,
    rules: list[dict[str, Any]],
) -> bool:
    """Run one weather-delayed rule when conditions become safe."""
    for rule in rules:
        pending = rule.get("pending_catch_up")
        if not isinstance(pending, dict):
            continue
        deadline = _parse_iso(pending.get("deadline"))
        if deadline is None or current > deadline:
            rule["pending_catch_up"] = None
            await _async_save_maps(hass, coordinator, schedules=rules)
            hass.bus.async_fire(
                EVENT_SCHEDULE_SKIPPED,
                {
                    "serial_number": _serial(coordinator),
                    "schedule_id": str(rule.get("id") or ""),
                    "summary": str(rule.get("summary") or "ANTHBOT app schedule"),
                    "reason": "catch_up_expired",
                    "scheduled_for": pending.get("scheduled_for"),
                },
            )
            continue
        next_check = _parse_iso(pending.get("next_check"))
        if next_check and current < next_check:
            continue
        reason = await _async_weather_block_reason(hass, rule, current)
        if reason:
            if _mower_busy(coordinator):
                await hass.services.async_call(
                    DOMAIN,
                    SERVICE_RETURN_TO_DOCK,
                    {ATTR_SERIAL_NUMBER: _serial(coordinator)},
                    blocking=True,
                )
            pending["reason"] = reason
            pending["next_check"] = (current + timedelta(minutes=5)).isoformat()
            await _async_save_maps(hass, coordinator, schedules=rules)
            return False

        rule["pending_catch_up"] = None
        await _async_save_maps(hass, coordinator, schedules=rules)
        event_data = {
            "serial_number": _serial(coordinator),
            "schedule_id": str(rule.get("id") or ""),
            "summary": str(rule.get("summary") or "ANTHBOT app schedule"),
            "mode": str(rule.get("mode") or "full"),
            "zones": rule.get("zones"),
            "mow_height": rule.get("mow_height"),
            "scheduled_for": pending.get("scheduled_for"),
            "started_at": current.isoformat(),
            "catch_up": True,
        }
        try:
            await _async_run_mode(
                hass,
                coordinator,
                event_data["mode"],
                rule.get("zones"),
                rule.get("mow_height"),
            )
        except Exception as err:
            hass.bus.async_fire(
                EVENT_SCHEDULE_ERROR,
                {**event_data, "error": f"{type(err).__name__}: {err}"},
            )
            raise
        hass.bus.async_fire(EVENT_SCHEDULE_TRIGGERED, event_data)
        return True
    return False


async def async_tick(hass: HomeAssistant, coordinator, now: datetime | None = None) -> None:
    current = dt_util.as_local(now or dt_util.now())
    rules, due = _due_rules(coordinator, current)
    override = override_for(coordinator)
    if override:
        expires = _parse_iso(override.get("expires"))
        if expires and current >= expires:
            action = str(override.get("action") or "")
            await _async_save_maps(hass, coordinator, override=None)
            if action == "mow":
                await hass.services.async_call(
                    DOMAIN,
                    SERVICE_RETURN_TO_DOCK,
                    {ATTR_SERIAL_NUMBER: _serial(coordinator)},
                    blocking=True,
                )
            hass.bus.async_fire(
                EVENT_OVERRIDE_CHANGED,
                {
                    "serial_number": _serial(coordinator),
                    "action": "expired",
                    "previous_action": action,
                },
            )
            _LOGGER.info("Anthbot override expired for %s", _serial(coordinator))
            return
        action = str(override.get("action") or "")
        if action == "park" and _mower_busy(coordinator):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RETURN_TO_DOCK,
                {ATTR_SERIAL_NUMBER: _serial(coordinator)},
                blocking=True,
            )
        await _async_mark_skipped(hass, coordinator, current, rules, due, "override_active")
        return
    for rule in due:
        hour, minute = parse_time(rule.get("start_time"))
        stamp = f"{current.date()} {hour:02d}:{minute:02d} {rule.get('id')}"
        # Persist before sending a mower command. A retry after a partial
        # command failure is more dangerous than recording one skipped run.
        rule["last_fired"] = stamp
        await _async_save_maps(hass, coordinator, schedules=rules)
        event_data = {
            "serial_number": _serial(coordinator),
            "schedule_id": str(rule.get("id") or ""),
            "summary": str(rule.get("summary") or "ANTHBOT app schedule"),
            "mode": str(rule.get("mode") or "full"),
            "zones": rule.get("zones"),
            "mow_height": rule.get("mow_height"),
            "scheduled_for": current.isoformat(),
        }
        weather_reason = await _async_weather_block_reason(hass, rule, current)
        if weather_reason:
            catch_up_hours = float(rule.get("catch_up_hours") or 0)
            if catch_up_hours > 0:
                rule["pending_catch_up"] = {
                    "scheduled_for": current.isoformat(),
                    "deadline": (
                        current + timedelta(hours=catch_up_hours)
                    ).isoformat(),
                    "next_check": (current + timedelta(minutes=5)).isoformat(),
                    "reason": weather_reason,
                }
            await _async_save_maps(hass, coordinator, schedules=rules)
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RETURN_TO_DOCK,
                {ATTR_SERIAL_NUMBER: _serial(coordinator)},
                blocking=True,
            )
            hass.bus.async_fire(
                EVENT_SCHEDULE_SKIPPED,
                {
                    **event_data,
                    "reason": weather_reason,
                    "catch_up_pending": catch_up_hours > 0,
                },
            )
            return
        # The mower firmware owns native appointments and starts them without a
        # second HA command.  Emitting a duplicate start here can create two
        # tasks, so HA only records that the app schedule became due.
        hass.bus.async_fire(
            EVENT_SCHEDULE_TRIGGERED,
            {**event_data, "source": "anthbot_app", "command_sent": False},
        )
        return
    # A native appointment can change the mower to "mowing" just before this
    # 30-second tick.  Therefore due rules (especially weather holds) must be
    # evaluated before the general busy guard.  Catch-up starts, however,
    # still wait until the mower is idle.
    if _mower_busy(coordinator):
        return
    if await _async_process_catch_up(hass, coordinator, current, rules):
        return


@callback
def async_start_schedule_engine(hass: HomeAssistant) -> None:
    if hass.data.get(DATA_UNSUB):
        return

    async def _interval(_now) -> None:
        domain_data = hass.data.get(DOMAIN, {})
        for entry_id, coordinators in list(domain_data.items()):
            if not isinstance(coordinators, list):
                continue
            for coordinator in coordinators:
                try:
                    await async_refresh_native_plan(coordinator)
                    await async_tick(hass, coordinator)
                except Exception:  # noqa: BLE001
                    _LOGGER.exception(
                        "ANTHBOT schedule mirror tick failed for %s",
                        getattr(getattr(coordinator, "client", None), "serial_number", "?"),
                    )

    hass.data[DATA_UNSUB] = async_track_time_interval(
        hass, _interval, timedelta(seconds=30)
    )


@callback
def async_stop_schedule_engine(hass: HomeAssistant) -> None:
    unsub = hass.data.pop(DATA_UNSUB, None)
    if unsub:
        unsub()
