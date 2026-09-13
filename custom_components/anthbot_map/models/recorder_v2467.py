"""Recorder compatibility repair for Anthbot Map v2.4.6.7.

Home Assistant combines an entity class' ``_unrecorded_attributes`` during
class construction and caches the result in a private combined set. The runtime
performance diagnostics were added later by a compatibility layer, so changing
``_unrecorded_attributes`` alone did not update Home Assistant's cached set.
That caused the rapidly changing ``runtime_performance`` Map attribute to be
written to Recorder every few seconds.

This module runs after performance diagnostics are installed and rebuilds the
cached combined set before Map entities are created. Live diagnostics remain
available in the current entity state, but Recorder no longer persists that
high-churn attribute.
"""

from __future__ import annotations

_INSTALLED = False


def install_recorder_v2467() -> None:
    """Refresh Home Assistant's cached unrecorded attributes for the Map entity."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from .. import sensor as sensor_module

    map_entity = sensor_module.AnthbotMapSensorEntity
    unrecorded = frozenset(
        set(map_entity._unrecorded_attributes) | {"runtime_performance"}
    )
    map_entity._unrecorded_attributes = unrecorded

    # Home Assistant computes this private cache in Entity.__init_subclass__.
    # The diagnostics compatibility layer modifies _unrecorded_attributes after
    # class creation, so explicitly refresh the same cache before entity setup.
    component_unrecorded = frozenset(
        getattr(map_entity, "_entity_component_unrecorded_attributes", frozenset())
    )
    map_entity._Entity__combined_unrecorded_attributes = (
        component_unrecorded | unrecorded
    )
