"""Restore M9/M9 Pro mowing-progress target fields after deferred trimming.

The v2.4.6.5 reliability layer trims ``mowing_progress`` attributes for every
model family.  The card's proven v2.4.6.4 target resolver needs the small
``active_zone_ids`` / ``learned_zone_mowing_key`` / ``last_mowing_task`` fields
in order to render "Full area" or the selected zone after the mower stops.

Genie already has a dedicated post-trim wrapper because it also needs a
percentage latch.  This module restores only the target metadata for M9/M9 Pro;
it does not change their native progress value, map/path logic, or other model
families.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from .base import model_family

_INSTALLED = False
_PATCHED = False
_CACHE_ATTR = "_m9_progress_target_presentation"
_M9_FAMILIES = {"m9", "m9_pro"}
_MOWING_RAW_STATES = {
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "bordermowing",
    "edgemowing",
    "regionmowing",
    "nestmowing",
    "spotmowing",
}


def _copy_task(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    task_type = value.get("type")
    if not isinstance(task_type, str) or not task_type:
        return None
    return deepcopy(value)


def _manual_task(ids: list[int]) -> dict[str, Any] | None:
    return {"type": "manual_zone", "data": {"id": list(ids)}} if ids else None


def _learned_task(value: Any) -> dict[str, Any] | None:
    key = str(value or "").strip().lower()
    if key == "full":
        return {"type": "full", "data": None}
    if not key.startswith("manual:"):
        return None
    ids: list[int] = []
    for item in key[len("manual:") :].split(","):
        try:
            zone_id = int(item.strip())
        except (TypeError, ValueError):
            continue
        if zone_id not in ids:
            ids.append(zone_id)
    return _manual_task(ids)


def _is_m9_progress(entity: Any) -> bool:
    description = getattr(entity, "entity_description", None)
    coordinator = getattr(entity, "coordinator", None)
    return (
        getattr(description, "key", None) == "mowing_progress"
        and model_family(getattr(getattr(coordinator, "device", None), "model", None))
        in _M9_FAMILIES
    )


def _patch_sensor_attributes() -> None:
    """Wrap the final post-reliability sensor attribute surface once."""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    from .. import sensor as sensor_module

    previous = sensor_module.AnthbotSensorEntity.extra_state_attributes.fget
    if previous is None:
        return

    def extra_state_attributes(self: Any) -> dict[str, Any]:
        attributes = dict(previous(self))
        if not _is_m9_progress(self):
            return attributes

        coordinator = self.coordinator
        state = coordinator.reported_state
        if not isinstance(state, dict):
            return attributes

        cache = getattr(coordinator, _CACHE_ATTR, None)
        if not isinstance(cache, dict):
            cache = {}
            setattr(coordinator, _CACHE_ATTR, cache)

        active = sensor_module._general_mower_status(state) == "mowing"  # noqa: SLF001
        raw = str(sensor_module._raw_robot_status(state) or "").strip().lower()  # noqa: SLF001
        if raw in _MOWING_RAW_STATES:
            active = True

        try:
            current_ids = list(sensor_module.active_manual_zone_ids(state))
        except Exception:  # noqa: BLE001 - presentation fallback must be fail-safe.
            current_ids = []

        try:
            learning = sensor_module._progress_learning_debug(state)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            learning = {}
        current_learned = learning.get("learned_zone_mowing_key")
        current_learned = (
            str(current_learned).strip()
            if current_learned not in (None, "")
            else None
        )

        try:
            _target, current_source = sensor_module._progress_target_area(state)  # noqa: SLF001
        except Exception:  # noqa: BLE001
            current_source = None
        current_source = (
            str(current_source).strip() if current_source not in (None, "") else None
        )

        current_task = _copy_task(getattr(coordinator, "last_mowing_task", None))
        if current_task is None:
            current_task = _manual_task(current_ids)
        if current_task is None:
            if raw == "globalmowing":
                current_task = {"type": "full", "data": None}
            elif raw in {"bordermowing", "edgemowing"}:
                current_task = {"type": "edge", "data": None}
            elif raw == "nestmowing":
                current_task = {"type": "dock_edge", "data": None}
        if current_task is None:
            current_task = _learned_task(current_learned)

        if active:
            cache["active_zone_ids"] = current_ids
            if current_learned:
                cache["learned_zone_mowing_key"] = current_learned
            if current_source:
                cache["progress_source"] = current_source
            if current_task is not None:
                cache["task"] = current_task

            exposed_ids = current_ids
            exposed_learned = current_learned
            exposed_source = current_source
            exposed_task = current_task
        else:
            exposed_ids = list(cache.get("active_zone_ids") or current_ids)
            exposed_learned = cache.get("learned_zone_mowing_key") or current_learned
            exposed_source = cache.get("progress_source") or current_source
            exposed_task = _copy_task(cache.get("task")) or current_task

        attributes["active_zone_ids"] = exposed_ids
        if exposed_learned:
            attributes["learned_zone_mowing_key"] = exposed_learned
        if exposed_source:
            attributes["progress_source"] = exposed_source
        if exposed_task is not None:
            attributes["last_mowing_task"] = exposed_task
        return attributes

    sensor_module.AnthbotSensorEntity.extra_state_attributes = property(
        extra_state_attributes
    )


def install_m9_progress_posttrim() -> None:
    """Schedule M9/M9 Pro target restoration after deferred reliability work."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: Any, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        _patch_sensor_attributes()

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init


__all__ = ["install_m9_progress_posttrim"]
