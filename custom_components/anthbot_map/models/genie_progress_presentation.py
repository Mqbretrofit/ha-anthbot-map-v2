"""Keep Genie mowing progress/target presentation stable after a task stops.

The live-map transport deliberately keeps Home Assistant state small.  The
v2.4.6.5 reliability layer also trims expensive progress-sensor diagnostics.
For Genie that removed the small target-identifying fields the card used in
v2.4.6.4 (active zone ids / learned target), while the raw progress value can
fall back to 0 as soon as the mower enters standby.

This layer restores only those presentation semantics for the Genie family:
while mowing it remembers the monotonic progress value and exact target, and
while stopped/returning/charging it exposes that last value until a new mowing
session starts.  M5/M9/N8 behaviour is untouched.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .base import model_family

_INSTALLED = False
_CACHE_ATTR = "_genie_progress_presentation"


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


def _infer_task(sensor_module: Any, state: dict[str, Any], coordinator: Any) -> dict[str, Any] | None:
    remembered = _copy_task(getattr(coordinator, "last_mowing_task", None))
    if remembered is not None:
        return remembered

    # Zone ids are the strongest fallback for tasks started outside HA.
    try:
        active_ids = list(sensor_module.active_manual_zone_ids(state))
    except Exception:  # noqa: BLE001 - presentation fallback must never break sensors.
        active_ids = []
    manual = _manual_task(active_ids)
    if manual is not None:
        return manual

    raw = sensor_module._raw_robot_status(state)  # noqa: SLF001
    if raw == "globalmowing":
        return {"type": "full", "data": None}
    if raw in {"bordermowing", "edgemowing"}:
        return {"type": "edge", "data": None}
    if raw == "nestmowing":
        return {"type": "dock_edge", "data": None}

    try:
        learning = sensor_module._progress_learning_debug(state)  # noqa: SLF001
    except Exception:  # noqa: BLE001
        learning = {}
    return _learned_task(learning.get("learned_zone_mowing_key"))


def install_genie_progress_presentation() -> None:
    """Install the Genie-only stopped-progress presentation latch."""
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
        active = sensor_module._general_mower_status(state) == "mowing"  # noqa: SLF001
        was_active = bool(cache.get("active"))
        numeric = _number(value)

        if active:
            if not was_active:
                # A real idle/return -> mowing transition starts a new session.
                # Reset the old percentage even when the fresh sensor begins at 0.
                cache.clear()
                cache["active"] = True
                if numeric is not None:
                    cache["progress"] = max(0.0, min(100.0, numeric))
            else:
                previous = _number(cache.get("progress"))
                # Progress is monotonic inside one task. Ignore a transient
                # zero/reset packet that can arrive just before standby status.
                if numeric is not None and (previous is None or numeric >= previous):
                    cache["progress"] = max(0.0, min(100.0, numeric))
            task = _infer_task(sensor_module, state, coordinator)
            if task is not None:
                cache["task"] = task
        else:
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
        active = sensor_module._general_mower_status(state) == "mowing"  # noqa: SLF001

        if active:
            task = _infer_task(sensor_module, state, coordinator)
            if task is not None:
                cache["task"] = task

            try:
                active_ids = list(sensor_module.active_manual_zone_ids(state))
            except Exception:  # noqa: BLE001
                active_ids = []
            cache["active_zone_ids"] = active_ids

            try:
                learning = sensor_module._progress_learning_debug(state)  # noqa: SLF001
            except Exception:  # noqa: BLE001
                learning = {}
            learned_key = learning.get("learned_zone_mowing_key")
            if learned_key:
                cache["learned_zone_mowing_key"] = learned_key

            source = attributes.get("progress_source")
            if source:
                cache["progress_source"] = source
        else:
            cache["active"] = False

        # Reliability trimming intentionally removes large diagnostics. Re-add
        # only the tiny fields required to render the exact mowing target.
        task = _copy_task(cache.get("task")) or _copy_task(
            getattr(coordinator, "last_mowing_task", None)
        )
        if task is not None:
            attributes["last_mowing_task"] = task

        if "active_zone_ids" in cache:
            attributes["active_zone_ids"] = list(cache.get("active_zone_ids") or [])
        if cache.get("learned_zone_mowing_key"):
            attributes["learned_zone_mowing_key"] = cache["learned_zone_mowing_key"]
        if not active and cache.get("progress_source"):
            attributes["progress_source"] = cache["progress_source"]

        attributes["progress_presentation_latched"] = (
            not active and _number(cache.get("progress")) is not None
        )
        return attributes

    sensor_module.AnthbotSensorEntity.native_value = property(native_value)
    sensor_module.AnthbotSensorEntity.extra_state_attributes = property(
        extra_state_attributes
    )


__all__ = ["install_genie_progress_presentation"]
