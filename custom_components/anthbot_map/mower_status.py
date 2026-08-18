"""Shared Anthbot mower-status helpers."""

from __future__ import annotations

from typing import Any

ROBOT_STATUS_BY_CODE: tuple[str, ...] = (
    "idle",
    "pause",
    "charge",
    "sleep",
    "ota",
    "position",
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "mapping",
    "backtodock",
    "resume_point",
    "shutdown",
    "remotectrl",
    "factory",
    "sleep",
    "camera_cleaning",
    "gototarget",
    "bordermowing",
    "regionmowing",
    "nestmowing",
)

_MOWING_STATUSES = {
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "bordermowing",
    "regionmowing",
    "nestmowing",
    "mowing",
    "working",
    "cutting",
    "edgecutting",
    "gototarget",
}

_DOCKED_STATUSES = {"charge", "charging", "charge_start", "docked"}
_PAUSED_STATUSES = {
    "idle",
    "pause",
    "paused",
    "sleep",
    "shutdown",
    "standby",
}
_RETURNING_STATUSES = {"backtodock", "returning", "returningtodock"}
_ERROR_STATUSES = {"error", "fault", "failed"}


def unwrap_value(value: Any) -> Any:
    """Unwrap nested Anthbot value envelopes without looping forever."""
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value["value"]
    return value


def as_int(value: Any) -> int | None:
    """Convert an Anthbot scalar or value envelope to an integer."""
    value = unwrap_value(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _status_value(data: dict[str, Any]) -> Any:
    """Return mower status across Genie and M-series shadow layouts."""
    for key in ("robot_sta", "mower_status", "mode"):
        value = unwrap_value(data.get(key))
        if value is not None:
            return value

    service = data.get("_service_reported")
    if isinstance(service, dict):
        for key in ("robot_sta", "mower_status", "mode"):
            value = unwrap_value(service.get(key))
            if value is not None:
                return value
    return None


def raw_robot_status(data: dict[str, Any]) -> str | None:
    """Return a normalized raw mower status from the shadow payload."""
    value = _status_value(data)
    if isinstance(value, int):
        if 0 <= value < len(ROBOT_STATUS_BY_CODE):
            value = ROBOT_STATUS_BY_CODE[value]
        else:
            value = str(value)
    if not isinstance(value, str):
        return None
    return value.strip().lower().replace("-", "").replace("_", "").replace(" ", "")


def mower_activity_name(data: dict[str, Any]) -> str | None:
    """Map an Anthbot shadow payload to a Home Assistant mower activity name."""
    error_code = as_int(data.get("err_code"))
    if error_code is None:
        service = data.get("_service_reported")
        if isinstance(service, dict):
            error_code = as_int(service.get("err_code"))
            if error_code is None:
                error_code = as_int(service.get("error"))
    if error_code not in (None, 0):
        return "error"

    status = raw_robot_status(data)
    if status in _MOWING_STATUSES:
        return "mowing"
    if status in _DOCKED_STATUSES:
        return "docked"
    if status in _RETURNING_STATUSES:
        return "returning"
    if status in _PAUSED_STATUSES:
        return "paused"
    if status in _ERROR_STATUSES:
        return "error"
    return None
