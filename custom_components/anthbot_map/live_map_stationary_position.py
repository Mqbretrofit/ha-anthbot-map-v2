"""Conservative stationary-position semantics for live-map hardening.

A mower can remain at exactly the same coordinates for a long time while docked
or paused.  Without a protocol-level pose timestamp, unchanged x/y values must
not be relabelled as fresh telemetry, but they also should not make the robot
vanish from the map.  Keep such evidence explicitly labelled as ``last_known``
or ``known_dock`` while active mowing/returning still ages to ``stale``.
"""

from __future__ import annotations

from typing import Any

from . import live_map_hardening as hardening
from .mower_status import mower_activity_name

_INSTALLED = False


def _display_pose(record: Any, *, keep_heading: bool) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    x = hardening._finite_number(record.get("x"))  # noqa: SLF001
    y = hardening._finite_number(record.get("y"))  # noqa: SLF001
    if x is None or y is None:
        return None
    pose: dict[str, Any] = {"x": x, "y": y}
    if keep_heading:
        heading = hardening._finite_number(record.get("heading"))  # noqa: SLF001
        if heading is not None:
            pose["heading"] = heading
    return pose


def install_stationary_position_semantics() -> None:
    """Keep stationary historical evidence visible without calling it current."""
    global _INSTALLED
    if _INSTALLED:
        return

    previous = hardening._position_attributes  # noqa: SLF001

    def position_attributes(hub: Any, state: dict[str, Any], *, now: float) -> dict[str, Any]:
        attributes = previous(hub, state, now=now)
        if attributes.get("position_status") != "stale":
            return attributes

        activity = mower_activity_name(state)
        record: Any = None
        status: str | None = None
        keep_heading = False

        if activity == "docked":
            record = attributes.get("known_dock_pose") or attributes.get("last_known_pose")
            if attributes.get("known_dock_pose") is not None:
                status = "known_dock"
                keep_heading = True
            elif record is not None:
                status = "last_known"
        elif activity == "paused":
            record = attributes.get("last_known_pose")
            if record is not None:
                status = "last_known"

        pose = _display_pose(record, keep_heading=keep_heading)
        if status is None or pose is None:
            return attributes

        attributes["position_status"] = status
        attributes["pose"] = pose
        attributes["cur_pose"] = pose
        attributes["map_scan_pose"] = None
        return attributes

    hardening._position_attributes = position_attributes  # noqa: SLF001
    _INSTALLED = True


__all__ = ["install_stationary_position_semantics"]
