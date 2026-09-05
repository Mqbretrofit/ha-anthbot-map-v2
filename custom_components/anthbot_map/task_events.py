"""Helpers for Anthbot cloud task events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

TASK_START_CODES = {1015, 1017, 1018, 1037}
TASK_FINISHED_CODE = 1014
LOW_BATTERY_RETURN_CODE = 1021
RAIN_RETURN_CODE = 1036
RAIN_RESUME_CODE = 1037


def task_event_items(payload: Any) -> list[dict[str, Any]]:
    """Return event dictionaries from known nested cloud response shapes."""
    current = payload
    for _ in range(4):
        if isinstance(current, list):
            return [item for item in current if isinstance(item, dict)]
        if not isinstance(current, dict):
            return []
        child = current.get("data")
        if child is current:
            return []
        current = child
    return []


def latest_task_event(payload: Any) -> dict[str, Any] | None:
    """Return the newest event; the cloud endpoint is newest-first."""
    items = task_event_items(payload)
    return items[0] if items else None


def task_event_value(payload: Any, key: str) -> Any:
    """Read one field from the newest task event."""
    event = latest_task_event(payload)
    return event.get(key) if event is not None else None


def _event_code(event: dict[str, Any]) -> int | None:
    value = event.get("code")
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def task_event_code(payload: Any) -> int | None:
    """Return the newest event code as an integer."""
    event = latest_task_event(payload)
    return _event_code(event) if event is not None else None


def task_event_datetime(payload: Any) -> datetime | None:
    """Parse the newest cloud event timestamp, which is supplied in UTC."""
    value = task_event_value(payload, "create_time")
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def latest_task_cycle_signal(payload: Any) -> str | None:
    """Classify the newest task event that changes battery-saver behavior."""
    for event in task_event_items(payload):
        code = _event_code(event)
        if code == TASK_FINISHED_CODE:
            return "completed"
        if code == LOW_BATTERY_RETURN_CODE:
            return "low_battery_return"
        if code == RAIN_RETURN_CODE:
            return "rain_return"
        if code in TASK_START_CODES:
            return "active"
    return None
