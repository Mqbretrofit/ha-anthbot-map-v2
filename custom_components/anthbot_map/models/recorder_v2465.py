"""Recorder-specific write throttling for Anthbot Map v2.4.6.5.

The coordinator keeps receiving live shadow updates at full speed.  This layer
only limits how often the always-ready Map entity writes a Home Assistant
state, because Recorder stores a state row whenever any visible entity
attribute changes even when that attribute itself is marked unrecorded.
"""

from __future__ import annotations

import time
from typing import Any

_INSTALLED = False
_MAP_STATE_MIN_SECONDS = 5.0


def install_recorder_v2465() -> None:
    """Reduce Recorder row churn without changing coordinator update cadence."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from .. import binary_sensor as binary_sensor_module
    from .. import sensor as sensor_module

    original_map_update = sensor_module.AnthbotMapSensorEntity._handle_coordinator_update

    def map_handle_coordinator_update(self: Any) -> None:
        now = time.monotonic()
        last = float(getattr(self, "_anthbot_last_map_state_write", 0.0) or 0.0)
        if last and now - last < _MAP_STATE_MIN_SECONDS:
            return
        self._anthbot_last_map_state_write = now
        original_map_update(self)

    sensor_module.AnthbotMapSensorEntity._handle_coordinator_update = (
        map_handle_coordinator_update
    )

    # reliability_v2465 already removes common fast-changing attributes from
    # all binary sensors.  Keep the no-go sensor useful while active, but retain
    # only episode-level values that change when the actual crossing evidence
    # changes; checked point/segment counters must not create one DB row per
    # incoming path point.
    original_binary_attributes = (
        binary_sensor_module.AnthbotBinarySensorEntity.extra_state_attributes.fget
    )
    if original_binary_attributes is not None:

        def binary_attributes(self: Any) -> dict[str, Any]:
            attributes = dict(original_binary_attributes(self))
            if self.entity_description.key != "no_go_path_crossing":
                return attributes
            keep = {
                "serial_number",
                "model",
                "path_id",
                "crossing_detected",
                "boundary_crossings",
                "points_inside",
                "traversals",
                "zone_ids",
            }
            return {key: value for key, value in attributes.items() if key in keep}

        binary_sensor_module.AnthbotBinarySensorEntity.extra_state_attributes = property(
            binary_attributes
        )
