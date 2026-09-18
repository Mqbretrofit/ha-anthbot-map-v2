"""Calendar mirror for ANTHBOT app schedules and HA overrides."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
import uuid

from homeassistant.components.calendar import CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .schedule_engine import async_add_rule, async_delete_rule, expand_events, parse_weekdays


def _description_options(value: object) -> dict[str, object]:
    """Parse optional mowing fields entered in the HA calendar description."""
    result: dict[str, object] = {}
    aliases = {
        "mode": "mode",
        "zones": "zones",
        "zone": "zones",
        "height": "mow_height",
        "mow_height": "mow_height",
        "weather": "weather_entity",
        "forecast": "forecast_guard_hours",
        "catchup": "catch_up_hours",
        "catch_up": "catch_up_hours",
        "rain_probability": "rain_probability",
    }
    numeric = {
        "mow_height",
        "forecast_guard_hours",
        "catch_up_hours",
        "rain_probability",
    }
    for part in re.split(r"[;\n]", str(value or "")):
        if "=" not in part:
            continue
        key, raw = (item.strip() for item in part.split("=", 1))
        target = aliases.get(key.casefold())
        if target is None or not raw:
            continue
        if target in numeric:
            try:
                result[target] = float(raw)
            except ValueError:
                continue
        else:
            result[target] = raw
    return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(AnthbotScheduleCalendar(coordinator) for coordinator in coordinators)


class AnthbotScheduleCalendar(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], CalendarEntity
):
    _attr_has_entity_name = True
    _attr_name = "Schedule"
    _attr_translation_key = "schedule"
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    )

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_schedule"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        events = expand_events(self.coordinator, now, now + timedelta(days=8))
        for item in events:
            if item["end"] > now:
                return CalendarEvent(
                    start=item["start"],
                    end=item["end"],
                    summary=item["summary"],
                    description=item["description"],
                    uid=item["uid"],
                )
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        return [
            CalendarEvent(
                start=item["start"],
                end=item["end"],
                summary=item["summary"],
                description=item["description"],
                uid=item["uid"],
            )
            for item in expand_events(self.coordinator, start_date, end_date)
        ]

    async def async_create_event(self, **kwargs) -> None:
        start = kwargs.get("dtstart") or kwargs.get("start")
        if start is None:
            return
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(
                start, time.min, tzinfo=dt_util.get_default_time_zone()
            )
        local = dt_util.as_local(start)
        end = kwargs.get("dtend") or kwargs.get("end")
        if isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(
                end, time.min, tzinfo=dt_util.get_default_time_zone()
            )
        duration_minutes = 60
        if isinstance(end, datetime):
            duration_minutes = max(
                15,
                int((dt_util.as_local(end) - local).total_seconds() // 60),
            )
        rrule = str(kwargs.get("rrule") or "")
        weekdays = [local.weekday()]
        if "FREQ=WEEKLY" in rrule.upper() and "BYDAY=" in rrule.upper():
            raw = rrule.upper().split("BYDAY=", 1)[1].split(";")[0]
            weekdays = parse_weekdays(
                raw.replace("MO", "mon").replace("TU", "tue").replace("WE", "wed")
                .replace("TH", "thu").replace("FR", "fri").replace("SA", "sat").replace("SU", "sun")
            )
        description_options = _description_options(kwargs.get("description"))
        await async_add_rule(
            self.hass,
            self.coordinator,
            {
                "id": str(kwargs.get("uid") or uuid.uuid4()),
                "summary": kwargs.get("summary") or "ANTHBOT app schedule",
                "weekdays": weekdays,
                "start_time": f"{local.hour:02d}:{local.minute:02d}",
                "mode": "full",
                "enabled": True,
                "duration_minutes": duration_minutes,
                **description_options,
            },
        )

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        if uid.startswith("override-") or uid.startswith("app-"):
            return
        await async_delete_rule(self.hass, self.coordinator, uid)
