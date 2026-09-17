"""Calendar platform for HA-owned Anthbot schedules and overrides."""

from __future__ import annotations

from datetime import datetime, timedelta
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
            if item["start"] <= now < item["end"]:
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
        local = dt_util.as_local(start)
        rrule = str(kwargs.get("rrule") or "")
        weekdays = [local.weekday()]
        if "FREQ=WEEKLY" in rrule.upper() and "BYDAY=" in rrule.upper():
            raw = rrule.upper().split("BYDAY=", 1)[1].split(";")[0]
            weekdays = parse_weekdays(
                raw.replace("MO", "mon").replace("TU", "tue").replace("WE", "wed")
                .replace("TH", "thu").replace("FR", "fri").replace("SA", "sat").replace("SU", "sun")
            )
        await async_add_rule(
            self.hass,
            self.coordinator,
            {
                "id": str(kwargs.get("uid") or uuid.uuid4()),
                "summary": kwargs.get("summary") or "HA schedule",
                "weekdays": weekdays,
                "start_time": f"{local.hour:02d}:{local.minute:02d}",
                "mode": "full",
                "enabled": True,
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
