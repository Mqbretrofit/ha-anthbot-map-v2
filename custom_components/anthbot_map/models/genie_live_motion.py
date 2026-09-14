"""Genie live-motion continuity matching M9/M9 Pro presentation semantics.

The M-series mower streams ``curpath`` while returning to the dock, so its
trajectory and pose continue to move on the card until docking completes.
Genie uses complete path snapshots requested with ``req_all_path``. Extend the
Genie-only path refresh gate to include return-to-dock motion, and promote the
pose aliases that some Genie firmware publishes on the service shadow.
"""

from __future__ import annotations

from typing import Any

from . import genie_live_path_refresh as _path_refresh
from . import genie_status as _genie_status

_INSTALLED = False

_RETURN_STATUS_VALUES = frozenset(
    {
        "backtodock",
        "returntodock",
        "returningtodock",
        "docking",
    }
)

# live_map_stream_core already understands these aliases. They only need to be
# promoted from the service shadow into the coordinator's normal property state
# so WebSocket subscribers see them immediately without a browser reload.
_GENIE_POSE_ALIASES = frozenset(
    {
        "curPose",
        "mapScanPose",
        "map_scan_pose",
    }
)


def _unwrap(value: Any) -> Any:
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def _normalize(value: Any) -> str:
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        try:
            # Genie robot status code 10 is the established back-to-dock state.
            if int(value) == 10 and float(value) == 10.0:
                return "backtodock"
        except (TypeError, ValueError, OverflowError):
            return ""
    if not isinstance(value, str):
        return ""
    return value.lower().replace("-", "").replace("_", "").replace(" ", "")


def _status_value(state: dict[str, Any]) -> Any:
    for key in ("robot_sta", "mower_status", "robot_status_raw", "mode"):
        value = _unwrap(state.get(key))
        if value not in (None, ""):
            return value
    return None


def _is_return_motion(state: dict[str, Any]) -> bool:
    if not isinstance(state, dict):
        return False
    return _normalize(_status_value(state)) in _RETURN_STATUS_VALUES


def install_genie_live_motion_support() -> None:
    """Keep Genie live path/pose updates active through the return-to-dock leg."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_is_live = _path_refresh._is_live_state  # noqa: SLF001

    def is_live_or_returning(state: dict[str, Any]) -> bool:
        return previous_is_live(state) or _is_return_motion(state)

    # The Genie path worker and its live-shadow wrapper resolve this module
    # global at call time, so extending it here keeps the already proven path
    # transport intact while adding only the missing return-to-dock phase.
    _path_refresh._is_live_state = is_live_or_returning  # noqa: SLF001

    # Genie service-shadow telemetry may use the same camelCase pose keys that
    # the stream core already accepts. Promote them just like pose/cur_pose.
    _genie_status._GENIE_LIVE_TELEMETRY_KEYS = frozenset(  # noqa: SLF001
        set(_genie_status._GENIE_LIVE_TELEMETRY_KEYS) | set(_GENIE_POSE_ALIASES)  # noqa: SLF001
    )


__all__ = ["install_genie_live_motion_support"]
