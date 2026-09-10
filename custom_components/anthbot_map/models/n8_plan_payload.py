"""Pure N8/MGS03 schedule/DND payload helpers.

The 2.15.16 app statically proves the `mow_regular` wire family, but Home
Assistant publishing remains intentionally disabled until a real N8
`time_setting.json` before/after capture confirms preservation semantics.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

PLAN_INCREMENT_MIN_FIRMWARE = (1, 16, 15)
PLAN_END_TIME_MIN_FIRMWARE = (1, 15, 13)


def _version_tuple(value: object) -> tuple[int, ...]:
    """Parse the numeric prefix of an ANTHBOT firmware version."""
    parts = str(value or "").strip().split(".")
    result: list[int] = []
    for part in parts:
        digits = ""
        for char in part:
            if char.isdigit():
                digits += char
            else:
                break
        if not digits:
            break
        result.append(int(digits))
    return tuple(result)


def _at_least(value: object, minimum: tuple[int, ...]) -> bool:
    parsed = _version_tuple(value)
    if not parsed:
        return False
    width = max(len(parsed), len(minimum))
    current = parsed + (0,) * (width - len(parsed))
    target = minimum + (0,) * (width - len(minimum))
    return current >= target


def supports_incremental_plan(firmware_version: object) -> bool:
    """Return the 2.15.16 app's mower-firmware incremental-plan gate."""
    return _at_least(firmware_version, PLAN_INCREMENT_MIN_FIRMWARE)


def supports_plan_end_time(firmware_version: object) -> bool:
    """Return the 2.15.16 app's mower-firmware end-time gate."""
    return _at_least(firmware_version, PLAN_END_TIME_MIN_FIRMWARE)


def build_dnd_entry(
    *,
    start_time: Any,
    end_time: Any,
    active: Any,
) -> dict[str, Any]:
    """Build the exact DND entry shape reconstructed from app 2.15.16."""
    return {
        "start_time": start_time,
        "end_time": end_time,
        "active": active,
        "unlock": 0,
        "week": [1, 2, 3, 4, 5, 6, 7],
        "repeat": 1,
        "workmode": 0,
    }


def build_full_plan_data(
    entries: Iterable[dict[str, Any]],
    *,
    timezone_sec: int,
) -> dict[str, Any]:
    """Build the proven full/legacy `mow_regular.data` envelope."""
    if isinstance(timezone_sec, bool) or not isinstance(timezone_sec, int):
        raise ValueError("timezone_sec must be an integer number of seconds")
    return {
        "timezone": timezone_sec / 3600,
        "timezone_sec": timezone_sec,
        "value": [dict(entry) for entry in entries],
    }


def build_incremental_plan_data(
    entries: Iterable[dict[str, Any]],
    *,
    timezone_sec: int,
    version: Any,
) -> dict[str, Any]:
    """Build the proven incremental `mow_regular.data` envelope.

    This helper only represents the wire shape. It deliberately does not decide
    which retained/changed entries belong in `value`; that behavior still needs
    a real N8 before/after capture before any public writer is enabled.
    """
    if version is None:
        raise ValueError("incremental plan payload requires a plan version")
    payload = build_full_plan_data(entries, timezone_sec=timezone_sec)
    payload["version"] = version
    return payload


def build_mow_regular_command(data: dict[str, Any]) -> dict[str, Any]:
    """Wrap already-built plan data in the recovered command object."""
    return {"cmd": "mow_regular", "data": dict(data)}


__all__ = [
    "PLAN_END_TIME_MIN_FIRMWARE",
    "PLAN_INCREMENT_MIN_FIRMWARE",
    "build_dnd_entry",
    "build_full_plan_data",
    "build_incremental_plan_data",
    "build_mow_regular_command",
    "supports_incremental_plan",
    "supports_plan_end_time",
]
