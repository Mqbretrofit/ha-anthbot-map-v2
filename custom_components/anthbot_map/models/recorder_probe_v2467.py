"""Temporary field probe for final v2.4.6.7 Map Recorder churn.

This module does not change write decisions. It wraps the final Map update
handler and reports which *final idle-semantic signature* fields changed
whenever the existing Recorder filters actually accept a Home Assistant state
write.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import recorder_v2467 as _recorder

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False

_SIGNATURE_NAMES = (
    "mower_status",
    "robot_status_raw",
    "pose",
    "cur_pose",
    "map_scan_pose",
    "path",
    "map_definition",
    "path_time",
    "area_time",
    "ridable_area_time",
    "area_definition",
    "ridable_area_definition",
    "history_path_info",
    "history_path_source",
    "history_path_live_refresh",
    "history_path_refresh_interval",
    "map_archive_selection",
    "map_definition_error",
    "path_definition_error",
    "ridable_area_definition_error",
    "cloud_connected",
    "robot_online",
    "live_shadow_connected",
    "cloud_error",
    "live_shadow_error",
    "mowing_records",
    "task_events",
    "error_history",
    "robot_maintenance",
    "last_mowing_task",
    "custom_button_actions_configured",
    "custom_button_actions_enabled",
    "custom_button_actions",
)


def _changed_names(previous: Any, current: tuple[Any, ...]) -> list[str]:
    if not isinstance(previous, tuple) or len(previous) != len(current):
        return ["initial"]
    return [
        _SIGNATURE_NAMES[index]
        if index < len(_SIGNATURE_NAMES)
        else f"field_{index}"
        for index, (old, new) in enumerate(zip(previous, current))
        if old != new
    ]


def install_recorder_probe_v2467() -> None:
    """Install logging-only wrapper around the final Map update handler."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from .. import sensor as sensor_module

    map_entity = sensor_module.AnthbotMapSensorEntity
    previous_update = map_entity._handle_coordinator_update

    def handle_coordinator_update(self: Any) -> None:
        now = time.monotonic()
        # Resolve dynamically: recorder_idle_semantics_v2467 replaces this
        # function during install, so this always observes the exact final
        # signature used by the write filter.
        signature = _recorder._map_live_signature(sensor_module, self.coordinator)  # noqa: SLF001
        previous_signature = getattr(self, "_anthbot_recorder_probe_signature", None)
        changed = _changed_names(previous_signature, signature)

        before_write = float(
            getattr(self, "_anthbot_last_map_state_write", 0.0) or 0.0
        )
        previous_update(self)
        after_write = float(
            getattr(self, "_anthbot_last_map_state_write", 0.0) or 0.0
        )

        if after_write != before_write:
            previous_probe_write = float(
                getattr(self, "_anthbot_recorder_probe_last_write", 0.0) or 0.0
            )
            delta = now - previous_probe_write if previous_probe_write else 0.0
            _LOGGER.warning(
                "ANTHBOT RECORDER PROBE2 serial=%s delta=%.2fs changed=%s",
                getattr(self.coordinator.client, "serial_number", "unknown"),
                delta,
                ",".join(changed) if changed else "heartbeat_or_internal",
            )
            self._anthbot_recorder_probe_last_write = now
            self._anthbot_recorder_probe_signature = signature

    map_entity._handle_coordinator_update = handle_coordinator_update


__all__ = ["install_recorder_probe_v2467"]
