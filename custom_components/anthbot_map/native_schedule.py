"""Native ANTHBOT app schedule parsing and write support.

The ANTHBOT 2.15.16 application uses the named service-shadow command
``mow_regular`` for both the Genie and MGS/Pion planner families.  Genie sends
the appointment list as ``value`` while M5/M9/N8/Pion sends incremental writes
as ``appointment`` (or ``delete_appointment``).  Keep every unknown object
field intact so model and firmware specific settings are never lost when Home
Assistant edits a rule.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import logging
import tarfile
import time
from typing import Any

from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)
_MGS_PLAN_RETRY_SECONDS = 300.0

WORKMODE_TO_MODE = {0: "full", 1: "zone", 4: "region"}
MODE_TO_WORKMODE = {
    "full": 0,
    "zone": 1,
    "auto_zone": 1,
    "region": 4,
}

_APPOINTMENT_FIELDS = {
    "active",
    "area_id",
    "area_points",
    "end_time",
    "repeat",
    "start_time",
    "unlock",
    "week",
    "workmode",
}


def _model_text(coordinator: Any) -> str:
    return str(getattr(getattr(coordinator, "device", None), "model", "") or "").upper()


def _is_mgs_family(coordinator: Any) -> bool:
    model = _model_text(coordinator)
    return any(token in model for token in ("M5", "M9", "MGS", "N8", "PION"))


def _is_pion_family(coordinator: Any) -> bool:
    return "PION" in _model_text(coordinator)


def _current_mow_height(coordinator: Any) -> int:
    state = getattr(coordinator, "reported_state", {})
    if isinstance(state, dict):
        for parent in ("param_set", "mow_remote"):
            value = state.get(parent)
            if isinstance(value, dict):
                height = _safe_int(value.get("cutter_height"), 0)
                if 20 <= height <= 100:
                    return height
    return 50


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _plan_from_value(value: Any) -> dict[str, Any] | None:
    """Normalize the appointment shapes used by Genie and MGS shadows."""
    if isinstance(value, str):
        try:
            return _plan_from_value(json.loads(value))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    if isinstance(value, list):
        return timezone_envelope(
            [deepcopy(item) for item in value if isinstance(item, dict)]
        )
    if not isinstance(value, dict):
        return None

    entries = value.get("value")
    if isinstance(entries, list):
        plan = deepcopy(value)
        plan["value"] = [deepcopy(item) for item in entries if isinstance(item, dict)]
        return plan

    # AWS IoT can wrap the actual appointment envelope in
    # {"value": <plan>, "timestamp": ...}.  It may also JSON-encode that
    # nested value.
    if isinstance(entries, (dict, str)):
        nested = _plan_from_value(entries)
        if nested is not None:
            return nested

    for key in ("appointment", "appointments", "plans", "schedule"):
        if key not in value:
            continue
        child = value.get(key)
        if isinstance(child, list):
            nested = {
                name: deepcopy(item)
                for name, item in value.items()
                if name != key
            }
            nested["value"] = [
                deepcopy(item) for item in child if isinstance(item, dict)
            ]
            defaults = timezone_envelope([])
            nested.setdefault("timezone", defaults["timezone"])
            nested.setdefault("timezone_sec", defaults["timezone_sec"])
            return nested
        nested = _plan_from_value(child)
        if nested is not None:
            return nested

    # Some Genie firmware reports one appointment object directly instead of
    # an envelope or list.
    if _APPOINTMENT_FIELDS.intersection(value):
        return timezone_envelope([deepcopy(value)])
    return None


def _shadow_scalar(value: Any) -> Any:
    """Unwrap a JSON/AWS scalar without accepting arbitrary containers."""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            decoded = json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return value
        return _shadow_scalar(decoded)
    if isinstance(value, dict) and "value" in value:
        return _shadow_scalar(value.get("value"))
    return value


def _appointment_revision(state: dict[str, Any]) -> Any:
    """Return the app-file revision announced by either shadow."""
    value = _shadow_scalar(state.get("appointment_time"))
    if value not in (None, "", 0, "0"):
        return value
    service = state.get("_service_reported")
    if isinstance(service, dict):
        value = _shadow_scalar(service.get("appointment_time"))
        if value not in (None, "", 0, "0"):
            return value
    return None


def native_plan_for(coordinator: Any) -> dict[str, Any]:
    """Return the app-native plan currently known by the coordinator."""
    state = getattr(coordinator, "reported_state", {})
    if isinstance(state, dict):
        plan = _plan_from_value(state.get("appointment"))
        if plan is not None and plan.get("value"):
            setattr(coordinator, "_anthbot_native_plan", deepcopy(plan))
            return plan
        service = state.get("_service_reported")
        if isinstance(service, dict):
            service_plan = _plan_from_value(service.get("appointment"))
            if service_plan is not None and service_plan.get("value"):
                setattr(coordinator, "_anthbot_native_plan", deepcopy(service_plan))
                return service_plan
    cached = _plan_from_value(getattr(coordinator, "_anthbot_native_plan", None))
    if cached is not None and cached.get("value"):
        return cached
    if isinstance(state, dict) and plan is not None:
        setattr(coordinator, "_anthbot_native_plan", deepcopy(plan))
        return plan
    if cached is not None:
        return cached
    return timezone_envelope([])


def _plan_id_from_state(state: dict[str, Any]) -> str | None:
    map_state = state.get("map")
    if not isinstance(map_state, dict):
        return None
    value = map_state.get("plan_id")
    return str(value) if value not in (None, "") else None


def _plan_from_time_setting(value: Any) -> dict[str, Any] | None:
    """Locate the known MGS full-plan envelope conservatively."""
    plan = _plan_from_value(value)
    if plan is not None:
        return plan
    if isinstance(value, list):
        return timezone_envelope(
            [deepcopy(item) for item in value if isinstance(item, dict)]
        )
    if not isinstance(value, dict):
        return None
    for key in ("appointment", "appointments", "plans", "schedule"):
        entries = value.get(key)
        if isinstance(entries, list):
            envelope = {
                name: deepcopy(item)
                for name, item in value.items()
                if name != key
            }
            envelope["value"] = deepcopy(entries)
            defaults = timezone_envelope([])
            envelope.setdefault("timezone", defaults["timezone"])
            envelope.setdefault("timezone_sec", defaults["timezone_sec"])
            return envelope
    for key in ("data", "plan", "time_setting"):
        nested = _plan_from_time_setting(value.get(key))
        if nested is not None:
            return nested
    return None


def _plan_from_map_manager(raw: bytes) -> dict[str, Any] | None:
    """Extract the MGS plan without unpacking untrusted archive paths."""
    if not raw or len(raw) > 64 * 1024 * 1024:
        return None
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as archive:
            for member in archive.getmembers():
                if (
                    not member.isfile()
                    or member.name.rsplit("/", 1)[-1] != "time_setting.json"
                    or member.size > 2 * 1024 * 1024
                ):
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    return None
                parsed = json.loads(extracted.read().decode("utf-8-sig"))
                return _plan_from_time_setting(parsed)
    except (
        tarfile.TarError,
        OSError,
        EOFError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ):
        return None
    return None


def _appointment_probe_details(definition: Any) -> dict[str, Any]:
    """Return a bounded, non-secret description of an appointment payload."""
    details: dict[str, Any] = {"payload_type": type(definition).__name__}
    if isinstance(definition, dict):
        details["keys"] = sorted(str(key) for key in definition)[:40]
        source = definition.get("_download_source")
        if isinstance(source, dict):
            details["download_source"] = {
                key: value
                for key, value in source.items()
                if key
                in {
                    "filename",
                    "category",
                    "sub_category",
                    "content_md5",
                    "expected_md5",
                    "md5_matches",
                }
            }
        binary = definition.get("_binary_probe")
        if isinstance(binary, dict):
            details["binary_probe"] = {
                key: binary.get(key)
                for key in ("label", "size", "first_bytes", "decode_errors")
                if key in binary
            }
    elif isinstance(definition, list):
        details["item_count"] = len(definition)
        first = next((item for item in definition if isinstance(item, dict)), None)
        if first is not None:
            details["first_item_keys"] = sorted(str(key) for key in first)[:40]
    return details


def _publish_appointment_probe(
    coordinator: Any,
    state: dict[str, Any],
    probe: dict[str, Any],
) -> None:
    """Expose the read-only appointment-file result for field diagnostics."""
    updated = dict(state)
    updated["_native_schedule_probe"] = probe
    coordinator.async_set_updated_data(updated)


async def async_refresh_native_plan(coordinator: Any) -> bool:
    """Load the app plan file when the mower shadow only announces a revision.

    Genie app 2.15.16 uses ``appointment_time`` as the revision trigger for
    ``appointment_<serial>.json``.  M5/M9/N8/Pion builds can instead keep the
    same envelope in ``time_setting.json``.  Both downloads are read-only and
    bounded so an unavailable cloud file cannot cause request churn.
    """
    state = getattr(coordinator, "reported_state", {})
    if not isinstance(state, dict):
        return False
    direct = _plan_from_value(state.get("appointment"))
    service = state.get("_service_reported")
    service_plan = (
        _plan_from_value(service.get("appointment"))
        if isinstance(service, dict)
        else None
    )
    if (direct is not None and direct.get("value")) or (
        service_plan is not None and service_plan.get("value")
    ):
        return False

    revision = _appointment_revision(state)
    now = time.monotonic()
    if revision is not None:
        last_revision = getattr(
            coordinator, "_anthbot_appointment_file_revision", None
        )
        last_probe = float(
            getattr(
                coordinator,
                "_anthbot_appointment_file_probe_monotonic",
                0.0,
            )
            or 0.0
        )
        appointment_probe_due = not (
            last_probe
            and revision == last_revision
            and now - last_probe < _MGS_PLAN_RETRY_SECONDS
        )
        if appointment_probe_due:
            setattr(coordinator, "_anthbot_appointment_file_revision", revision)
            setattr(coordinator, "_anthbot_appointment_file_probe_monotonic", now)
            try:
                definition = (
                    await coordinator.account_client.async_get_device_appointment_definition(
                        coordinator.client.serial_number
                    )
                )
                plan = _plan_from_time_setting(definition)
                if plan is not None:
                    setattr(coordinator, "_anthbot_native_plan", deepcopy(plan))
                    updated = dict(state)
                    updated["appointment"] = deepcopy(plan)
                    updated["_native_schedule_probe"] = {
                        "status": "loaded",
                        "revision": revision,
                        "entry_count": len(plan.get("value", [])),
                        **_appointment_probe_details(definition),
                    }
                    coordinator.async_set_updated_data(updated)
                    return True
                _publish_appointment_probe(
                    coordinator,
                    state,
                    {
                        "status": "parse_failed",
                        "revision": revision,
                        **_appointment_probe_details(definition),
                    },
                )
            except Exception as err:  # noqa: BLE001 - optional cloud mirror.
                _publish_appointment_probe(
                    coordinator,
                    state,
                    {
                        "status": "download_failed",
                        "revision": revision,
                        "error_type": type(err).__name__,
                        "error": str(err)[:500],
                    },
                )
                _LOGGER.debug(
                    "Could not refresh Genie appointment file for %s: %s",
                    getattr(
                        getattr(coordinator, "client", None),
                        "serial_number",
                        "?",
                    ),
                    err,
                )

    if not _is_mgs_family(coordinator):
        return False

    plan_id = _plan_id_from_state(state)
    last_id = getattr(coordinator, "_anthbot_native_plan_probe_id", None)
    last_probe = float(
        getattr(coordinator, "_anthbot_native_plan_probe_monotonic", 0.0) or 0.0
    )
    if last_probe and plan_id == last_id and now - last_probe < _MGS_PLAN_RETRY_SECONDS:
        return False
    setattr(coordinator, "_anthbot_native_plan_probe_id", plan_id)
    setattr(coordinator, "_anthbot_native_plan_probe_monotonic", now)

    try:
        # Local import avoids coupling the Genie path to the experimental map
        # decoder at integration import time.
        from .models import m_series_map

        raw, _source = await m_series_map._download_current_map_manager(  # noqa: SLF001
            coordinator.account_client, coordinator.client.serial_number
        )
        plan = _plan_from_map_manager(raw)
        if plan is None:
            return False
        setattr(coordinator, "_anthbot_native_plan", deepcopy(plan))
        updated = dict(state)
        updated["appointment"] = deepcopy(plan)
        coordinator.async_set_updated_data(updated)
        return True
    except Exception as err:  # noqa: BLE001 - read-only fallback must not break updates.
        _LOGGER.debug(
            "Could not refresh native ANTHBOT plan for %s: %s",
            getattr(getattr(coordinator, "client", None), "serial_number", "?"),
            err,
        )
        return False


def timezone_envelope(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the exact timezone envelope used by app 2.15.16."""
    local_now = dt_util.as_local(dt_util.now())
    offset = local_now.utcoffset()
    timezone_sec = int(offset.total_seconds()) if offset is not None else 0
    return {
        "timezone": timezone_sec / 3600,
        "timezone_sec": timezone_sec,
        "value": deepcopy(entries),
    }


def _entry_key(entry: dict[str, Any], index: int) -> str:
    native_id = entry.get("id")
    if native_id not in (None, ""):
        return str(native_id)
    stable = {
        key: entry.get(key)
        for key in (
            "start_time",
            "end_time",
            "week",
            "repeat",
            "workmode",
            "area_id",
            "area_points",
            "unlock",
        )
    }
    digest = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()[:16]
    # Do not include the list index: deleting an earlier id-less Genie/Pion
    # rule must not change every later HA metadata key.
    return f"native-{digest}"


def _weekday_list(value: Any) -> list[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return [weekday for weekday in range(7) if value & (1 << weekday)]
    if not isinstance(value, (list, tuple, set)):
        return []
    numbers = [_safe_int(item, -1) for item in value]
    zero_based = 0 in numbers
    result: list[int] = []
    for number in numbers:
        if zero_based and 0 <= number <= 6:
            result.append(number)
        elif not zero_based and 1 <= number <= 7:
            result.append(number - 1)
    return sorted(set(result))


def _time_text(value: Any) -> str:
    if isinstance(value, str) and ":" in value:
        parts = value.split(":")
        try:
            return f"{int(parts[0]) % 24:02d}:{int(parts[1]) % 60:02d}"
        except (TypeError, ValueError):
            return "00:00"
    seconds = _safe_int(value)
    # Repeating app appointments store seconds from local midnight.  A
    # one-shot entry may contain an epoch timestamp; display its local time.
    if seconds >= 86_400:
        try:
            stamp = dt_util.as_local(dt_util.utc_from_timestamp(seconds))
            return f"{stamp.hour:02d}:{stamp.minute:02d}"
        except (OverflowError, OSError, ValueError):
            pass
    seconds %= 86_400
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}"


def _zone_text(entry: dict[str, Any]) -> str | None:
    zones = entry.get("area_id")
    if isinstance(zones, list):
        values = [str(value) for value in zones if value not in (None, "")]
        return ",".join(values) or None
    if zones not in (None, ""):
        return str(zones)
    return None


def native_rules_for(
    coordinator: Any,
    metadata: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Normalize native app appointments for HA calendar/card consumers."""
    plan = native_plan_for(coordinator)
    metadata_by_id = {
        str(item.get("id")): item
        for item in metadata or []
        if isinstance(item, dict) and item.get("id") not in (None, "")
    }
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(plan.get("value", [])):
        if not isinstance(raw, dict) or _safe_int(raw.get("unlock"), 1) == 0:
            continue
        schedule_id = _entry_key(raw, index)
        extra = metadata_by_id.get(schedule_id, {})
        workmode = _safe_int(raw.get("workmode"), 0)
        repeating = _safe_int(raw.get("repeat"), 1) != 0
        start_seconds = _safe_int(raw.get("start_time"), 0)
        start_datetime = None
        if not repeating and start_seconds >= 86_400:
            try:
                start_datetime = dt_util.as_local(
                    dt_util.utc_from_timestamp(start_seconds)
                ).isoformat()
            except (OverflowError, OSError, ValueError):
                pass
        result.append(
            {
                "id": schedule_id,
                "summary": str(extra.get("summary") or f"ANTHBOT app schedule {index + 1}"),
                "weekdays": _weekday_list(raw.get("week")),
                "start_time": _time_text(raw.get("start_time")),
                "start_datetime": start_datetime,
                "repeating": repeating,
                "mode": WORKMODE_TO_MODE.get(workmode, f"workmode_{workmode}"),
                "zones": _zone_text(raw),
                "mow_height": raw.get("cutter_height"),
                "enabled": bool(_safe_int(raw.get("active"), 1)),
                "duration_minutes": _safe_int(extra.get("duration_minutes"), 60),
                "weather_entity": extra.get("weather_entity"),
                "forecast_guard_hours": extra.get("forecast_guard_hours", 0),
                "rain_probability": extra.get("rain_probability", 50),
                "catch_up_hours": extra.get("catch_up_hours", 0),
                "pending_catch_up": extra.get("pending_catch_up"),
                "last_fired": extra.get("last_fired"),
                "source": "anthbot_app",
                "native": True,
                "native_version": plan.get("version"),
                "_native_index": index,
                "_native_raw": deepcopy(raw),
            }
        )
    return result


def _seconds_from_time(value: Any) -> int:
    text = str(value or "07:00")
    parts = text.split(":")
    if len(parts) < 2:
        raise ValueError("start_time must use HH:MM format")
    hour = int(parts[0])
    minute = int(parts[1])
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("start_time must be a valid local time")
    return hour * 3600 + minute * 60


def _native_weekdays(value: Any) -> list[int]:
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    result: list[int] = []
    for item in value or []:
        number = _safe_int(item, -1)
        if 0 <= number <= 6:
            result.append(number + 1)
    if not result:
        raise ValueError("At least one weekday is required")
    return sorted(set(result))


def _zone_values(value: Any) -> list[Any]:
    if isinstance(value, str):
        values: list[Any] = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, list):
        values = [item for item in value if item not in (None, "")]
    else:
        values = []
    result: list[Any] = []
    for item in values:
        text = str(item).strip()
        result.append(int(text) if text.lstrip("-").isdigit() else text)
    return result


def build_native_entry(
    coordinator: Any,
    rule: dict[str, Any],
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build/update an app appointment while preserving unknown fields."""
    entry = deepcopy(previous) if isinstance(previous, dict) else {}
    mode = str(rule.get("mode") or WORKMODE_TO_MODE.get(_safe_int(entry.get("workmode")), "full"))
    if mode not in MODE_TO_WORKMODE:
        raise ValueError(f"The ANTHBOT app scheduler does not support mode '{mode}'")
    workmode = MODE_TO_WORKMODE[mode]
    zones = _zone_values(rule.get("zones"))
    if workmode == 1 and not zones:
        raise ValueError("Zone schedules require at least one native ANTHBOT area id")
    if workmode == 4 and not entry.get("area_points"):
        raise ValueError("Mapped-region schedules must first be created in the ANTHBOT app")

    entry.update(
        {
            "start_time": _seconds_from_time(rule.get("start_time")),
            "active": 1 if bool(rule.get("enabled", True)) else 0,
            "unlock": 1,
            "week": _native_weekdays(rule.get("weekdays")),
            "repeat": 1,
            "workmode": workmode,
        }
    )
    if rule.get("mow_height") not in (None, ""):
        entry["cutter_height"] = int(rule["mow_height"])
    elif "cutter_height" not in entry:
        entry["cutter_height"] = _current_mow_height(coordinator)

    if _is_pion_family(coordinator):
        if workmode != 0:
            raise ValueError("Pion app schedules currently support full-lawn mode only")
        entry.setdefault("end_time", 0)
        entry.setdefault("cutter_direction", 0)
    elif _is_mgs_family(coordinator):
        if workmode == 1:
            entry["area_id"] = zones
            entry.setdefault("area_points", [])
        elif workmode == 4:
            entry.setdefault("area_id", [])
            entry.setdefault("area_points", [])
        else:
            entry["area_id"] = []
            entry["area_points"] = []
        entry.setdefault("end_time", 0)
        entry.setdefault("use_end_time", 0)
    else:
        entry.setdefault("end_time", 0)
        entry.setdefault("use_end_time", 0)
    return entry


def find_native_entry(
    plan: dict[str, Any], schedule_id: str
) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(plan.get("value", [])):
        if not isinstance(item, dict) or _safe_int(item.get("unlock"), 1) == 0:
            continue
        if _entry_key(item, index) == str(schedule_id):
            return index, item
    return None


def _command_data(
    plan: dict[str, Any],
    *,
    entries: list[dict[str, Any]],
    deleted_ids: list[Any] | None = None,
    mgs_family: bool = False,
) -> dict[str, Any]:
    base = timezone_envelope(entries)
    base["timezone"] = plan.get("timezone", base["timezone"])
    base["timezone_sec"] = plan.get("timezone_sec", base["timezone_sec"])
    if mgs_family:
        # App 2.15.16 uses incremental MGS/Pion payloads.  It never sends the
        # Genie ``value`` envelope for these models.
        base.pop("value", None)
        if entries:
            base["appointment"] = deepcopy(entries)
        if deleted_ids:
            base["delete_appointment"] = list(deleted_ids)
        return base
    if plan.get("version") not in (None, "", 0):
        base["version"] = plan["version"]
        if deleted_ids:
            base["delete_appointment"] = list(deleted_ids)
    return base


async def async_publish_native_plan_change(
    coordinator: Any,
    *,
    operation: str,
    schedule_id: str | None = None,
    entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish one app-native add/edit/delete and update the local mirror."""
    plan = native_plan_for(coordinator)
    values = [deepcopy(item) for item in plan.get("value", []) if isinstance(item, dict)]
    found = find_native_entry(plan, schedule_id or "") if schedule_id else None
    incremental = plan.get("version") not in (None, "", 0)
    mgs_family = _is_mgs_family(coordinator)

    if operation in {"add", "edit"}:
        if entry is None:
            raise ValueError("A native appointment is required")
        entry = deepcopy(entry)
        if operation == "add" and mgs_family and entry.get("id") in (None, ""):
            numeric_ids = [
                _safe_int(item.get("id"), 0)
                for item in values
                if isinstance(item, dict)
            ]
            entry["id"] = max(numeric_ids, default=0) + 1
        if found is None:
            values.append(deepcopy(entry))
        else:
            values[found[0]] = deepcopy(entry)
        data = _command_data(
            plan,
            entries=[entry] if (incremental or mgs_family) else values,
            mgs_family=mgs_family,
        )
    elif operation == "delete":
        if found is None:
            raise ValueError(f"Native ANTHBOT schedule '{schedule_id}' was not found")
        native_id = found[1].get("id")
        values.pop(found[0])
        if (incremental or mgs_family) and native_id not in (None, ""):
            data = _command_data(
                plan,
                entries=[],
                deleted_ids=[native_id],
                mgs_family=mgs_family,
            )
        elif mgs_family:
            raise ValueError("M-series native schedules require a numeric id")
        else:
            data = _command_data(plan, entries=values)
            data.pop("version", None)
    else:
        raise ValueError(f"Unsupported native schedule operation: {operation}")

    await coordinator.client.async_publish_service_command(cmd="mow_regular", data=data)

    mirrored = deepcopy(plan)
    mirrored["timezone"] = data["timezone"]
    mirrored["timezone_sec"] = data["timezone_sec"]
    mirrored["value"] = values
    setattr(coordinator, "_anthbot_native_plan", deepcopy(mirrored))
    state = dict(getattr(coordinator, "reported_state", {}) or {})
    state["appointment"] = mirrored
    state["_native_schedule_sync"] = {
        "status": "command_sent",
        "operation": operation,
        "requested_at": dt_util.now().isoformat(),
    }
    coordinator.async_set_updated_data(state)
    return mirrored


__all__ = [
    "async_refresh_native_plan",
    "build_native_entry",
    "find_native_entry",
    "native_plan_for",
    "native_rules_for",
    "async_publish_native_plan_change",
]
