"""Restore the v2.4.6.4 Genie mowing-progress presentation semantics.

v2.4.6.4 let the card resolve the mowing target from Home Assistant state:
``last_mowing_task`` first, then ``active_zone_ids``, then the learned target
key / progress source.  The v2.4.6.5 reliability layer intentionally trimmed
most progress diagnostics, so later frontend code started guessing/caching the
label locally.  Keep the live-map transport out of presentation instead and
restore the small v2.4.6.4 target fields at the sensor boundary.

Genie can also reset its raw session area as soon as it stops.  Preserve the
last monotonic percentage for the just-finished Genie task, but leave target
resolution to the proven v2.4.6.4 card/calibration code.  Other mower families
are untouched.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .base import model_family

_INSTALLED = False
_CACHE_ATTR = "_genie_progress_presentation"
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


def _is_genie_progress_entity(entity: Any) -> bool:
    coordinator = getattr(entity, "coordinator", None)
    description = getattr(entity, "entity_description", None)
    return (
        getattr(description, "key", None) == "mowing_progress"
        and model_family(getattr(getattr(coordinator, "device", None), "model", None))
        == "genie"
    )


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _cache(coordinator: Any) -> dict[str, Any]:
    value = getattr(coordinator, _CACHE_ATTR, None)
    if not isinstance(value, dict):
        value = {"active": False}
        setattr(coordinator, _CACHE_ATTR, value)
    return value


def _copy_task(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    task_type = value.get("type")
    if not isinstance(task_type, str) or not task_type:
        return None
    return deepcopy(value)


def _manual_task(ids: list[int]) -> dict[str, Any] | None:
    return {"type": "manual_zone", "data": {"id": list(ids)}} if ids else None


def _learned_task(learned_key: Any) -> dict[str, Any] | None:
    key = str(learned_key or "").strip().lower()
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


def _is_active(sensor_module: Any, state: dict[str, Any]) -> bool:
    if sensor_module._general_mower_status(state) == "mowing":  # noqa: SLF001
        return True
    raw = str(sensor_module._raw_robot_status(state) or "").strip().lower()  # noqa: SLF001
    return raw in _MOWING_RAW_STATES


def _current_target_data(
    sensor_module: Any,
    state: dict[str, Any],
    coordinator: Any,
) -> tuple[list[int], str | None, str | None, dict[str, Any] | None]:
    """Return the same small target evidence the v2.4.6.4 card consumed."""
    try:
        active_ids = list(sensor_module.active_manual_zone_ids(state))
    except Exception:  # noqa: BLE001 - presentation evidence must be fail-safe.
        active_ids = []

    try:
        learning = sensor_module._progress_learning_debug(state)  # noqa: SLF001
    except Exception:  # noqa: BLE001
        learning = {}
    learned_key = learning.get("learned_zone_mowing_key")
    learned_key = str(learned_key).strip() if learned_key not in (None, "") else None

    try:
        _target, progress_source = sensor_module._progress_target_area(state)  # noqa: SLF001
    except Exception:  # noqa: BLE001
        progress_source = None
    progress_source = (
        str(progress_source).strip() if progress_source not in (None, "") else None
    )

    task = _copy_task(getattr(coordinator, "last_mowing_task", None))
    if task is None:
        task = _manual_task(active_ids)
    if task is None:
        raw = str(sensor_module._raw_robot_status(state) or "").strip().lower()  # noqa: SLF001
        if raw == "globalmowing":
            task = {"type": "full", "data": None}
        elif raw in {"bordermowing", "edgemowing"}:
            task = {"type": "edge", "data": None}
        elif raw == "nestmowing":
            task = {"type": "dock_edge", "data": None}
    if task is None:
        task = _learned_task(learned_key)

    return active_ids, learned_key, progress_source, task


def install_genie_progress_presentation() -> None:
    """Install the Genie-only v2.4.6.4 progress/target compatibility layer."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from .. import sensor as sensor_module

    previous_native = sensor_module.AnthbotSensorEntity.native_value.fget
    previous_attributes = sensor_module.AnthbotSensorEntity.extra_state_attributes.fget
    if previous_native is None or previous_attributes is None:
        return

    def native_value(self: Any) -> Any:
        value = previous_native(self)
        if not _is_genie_progress_entity(self):
            return value

        coordinator = self.coordinator
        state = coordinator.reported_state
        if not isinstance(state, dict):
            return value

        cache = _cache(coordinator)
        active = _is_active(sensor_module, state)
        was_active = bool(cache.get("active"))
        numeric = _number(value)

        if active:
            if not was_active:
                # A real new mowing session replaces the previous session.
                cache.clear()
                cache["active"] = True
            previous = _number(cache.get("progress"))
            if numeric is not None and (previous is None or numeric >= previous):
                cache["progress"] = max(0.0, min(100.0, numeric))

            active_ids, learned_key, progress_source, task = _current_target_data(
                sensor_module, state, coordinator
            )
            cache["active_zone_ids"] = active_ids
            if learned_key:
                cache["learned_zone_mowing_key"] = learned_key
            if progress_source:
                cache["progress_source"] = progress_source
            if task is not None:
                cache["task"] = task
            return value

        cache["active"] = False
        latched = _number(cache.get("progress"))
        if latched is not None:
            return latched
        return value

    def extra_state_attributes(self: Any) -> dict[str, Any]:
        attributes = dict(previous_attributes(self))
        if not _is_genie_progress_entity(self):
            return attributes

        coordinator = self.coordinator
        state = coordinator.reported_state
        if not isinstance(state, dict):
            return attributes

        cache = _cache(coordinator)
        active = _is_active(sensor_module, state)
        active_ids, learned_key, progress_source, task = _current_target_data(
            sensor_module, state, coordinator
        )

        if active:
            cache["active"] = True
            cache["active_zone_ids"] = active_ids
            if learned_key:
                cache["learned_zone_mowing_key"] = learned_key
            if progress_source:
                cache["progress_source"] = progress_source
            if task is not None:
                cache["task"] = task
        else:
            cache["active"] = False

        # Restore the exact tiny v2.4.6.4 target evidence after the v2.4.6.5
        # Recorder/reliability trimming. During a finished task, prefer the
        # values captured while it was actually mowing over a generic idle
        # fallback such as learned_key == "full".
        if active:
            exposed_ids = active_ids
            exposed_learned = learned_key
            exposed_source = progress_source
            exposed_task = task
        else:
            exposed_ids = list(cache.get("active_zone_ids") or active_ids)
            exposed_learned = cache.get("learned_zone_mowing_key") or learned_key
            exposed_source = cache.get("progress_source") or progress_source
            exposed_task = _copy_task(cache.get("task")) or task

        attributes["active_zone_ids"] = exposed_ids
        if exposed_learned:
            attributes["learned_zone_mowing_key"] = exposed_learned
        if exposed_source:
            attributes["progress_source"] = exposed_source
        if exposed_task is not None:
            attributes["last_mowing_task"] = exposed_task

        attributes["progress_presentation_latched"] = (
            not active and _number(cache.get("progress")) is not None
        )
        return attributes

    sensor_module.AnthbotSensorEntity.native_value = property(native_value)
    sensor_module.AnthbotSensorEntity.extra_state_attributes = property(
        extra_state_attributes
    )


__all__ = ["install_genie_progress_presentation"]
