"""Low-overhead runtime activity diagnostics for support investigations.

The counters intentionally measure *activity*, not CPU percentage.  They make
runaway update loops visible without continuously running Python's profiler.
All data is kept in memory and reset when the config entry is reloaded.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_WINDOW_SECONDS = 60.0
_MIN_RATE_WINDOW_SECONDS = 10.0

# These are deliberately generous.  Normal activity is only written at DEBUG;
# a WARNING is emitted when a support-worthy runaway pattern is detected.
_SUSPICIOUS_PER_MINUTE = {
    "mqtt_shadow_updates": 3600.0,
    "coordinator_updates": 1800.0,
    "task_event_downloads": 30.0,
    "path_merges": 1800.0,
    "progress_sensor_evaluations": 3600.0,
    "progress_attribute_evaluations": 3600.0,
}

_COUNTER_KEYS = (
    "mqtt_shadow_updates",
    "mqtt_property_updates",
    "mqtt_service_updates",
    "coordinator_updates",
    "coordinator_refreshes",
    "task_event_refresh_attempts",
    "task_event_downloads",
    "path_merges",
    "progress_sensor_evaluations",
    "progress_attribute_evaluations",
)


def _blank_counts() -> dict[str, int]:
    return {key: 0 for key in _COUNTER_KEYS}


def _ensure_state(coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
    if hasattr(coordinator, "_runtime_perf_window_started"):
        return
    now = time.monotonic()
    coordinator._runtime_perf_started = now
    coordinator._runtime_perf_window_started = now
    coordinator._runtime_perf_window_counts = _blank_counts()
    coordinator._runtime_perf_totals = _blank_counts()
    coordinator._runtime_perf_last_window_seconds = 0.0
    coordinator._runtime_perf_last_window_counts = _blank_counts()
    coordinator._runtime_perf_last_window_rates = {
        key: 0.0 for key in _COUNTER_KEYS
    }
    coordinator._runtime_perf_last_status = "warming_up"


def _rate(count: int, elapsed: float) -> float | None:
    if elapsed < _MIN_RATE_WINDOW_SECONDS:
        return None
    return round(float(count) * 60.0 / elapsed, 2)


def _status_for_rates(rates: dict[str, float | None]) -> str:
    for key, threshold in _SUSPICIOUS_PER_MINUTE.items():
        value = rates.get(key)
        if value is not None and value > threshold:
            return "high_activity"
    return "normal"


def _roll_window(
    coordinator: AnthbotGenieDataUpdateCoordinator, now: float
) -> None:
    _ensure_state(coordinator)
    started = float(coordinator._runtime_perf_window_started)
    elapsed = max(0.0, now - started)
    if elapsed < _WINDOW_SECONDS:
        return

    counts = dict(coordinator._runtime_perf_window_counts)
    rates = {
        key: round(float(counts.get(key, 0)) * 60.0 / elapsed, 2)
        for key in _COUNTER_KEYS
    }
    status = _status_for_rates(rates)
    coordinator._runtime_perf_last_window_seconds = elapsed
    coordinator._runtime_perf_last_window_counts = counts
    coordinator._runtime_perf_last_window_rates = rates
    coordinator._runtime_perf_last_status = status
    coordinator._runtime_perf_window_started = now
    coordinator._runtime_perf_window_counts = _blank_counts()

    alias = str(getattr(coordinator.device, "alias", "Anthbot") or "Anthbot")
    model = str(getattr(coordinator.device, "model", "unknown") or "unknown")
    message = (
        "Anthbot runtime activity %s (%s): mqtt=%.1f/min, coordinator=%.1f/min, "
        "REST=%.1f/min, task_events=%.1f downloads/min, path_merges=%.1f/min, "
        "progress=%s/%s eval/min"
    )
    args = (
        alias,
        model,
        rates["mqtt_shadow_updates"],
        rates["coordinator_updates"],
        rates["coordinator_refreshes"],
        rates["task_event_downloads"],
        rates["path_merges"],
        rates["progress_sensor_evaluations"],
        rates["progress_attribute_evaluations"],
    )
    if status == "high_activity":
        _LOGGER.warning(message + " [HIGH ACTIVITY]", *args)
    else:
        _LOGGER.debug(message, *args)


def _record(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    key: str,
    amount: int = 1,
) -> None:
    if key not in _COUNTER_KEYS:
        return
    _ensure_state(coordinator)
    now = time.monotonic()
    _roll_window(coordinator, now)
    coordinator._runtime_perf_window_counts[key] += amount
    coordinator._runtime_perf_totals[key] += amount


def _snapshot(coordinator: AnthbotGenieDataUpdateCoordinator) -> dict[str, Any]:
    _ensure_state(coordinator)
    now = time.monotonic()
    _roll_window(coordinator, now)
    elapsed = max(0.001, now - float(coordinator._runtime_perf_window_started))
    counts = dict(coordinator._runtime_perf_window_counts)
    rates = {key: _rate(counts.get(key, 0), elapsed) for key in _COUNTER_KEYS}
    status = _status_for_rates(rates)

    # Every coordinator dispatch makes all normal sensors plus the map entity
    # eligible for a state write.  Estimate that fan-out without instrumenting
    # every entity individually, which would itself add overhead.
    try:
        from .. import sensor as sensor_platform

        entity_count = len(sensor_platform.SENSORS) + 1
    except Exception:  # pragma: no cover - support metadata must never break HA.
        entity_count = 0
    coordinator_rate = rates.get("coordinator_updates")
    estimated_entity_writes = (
        round(coordinator_rate * entity_count, 2)
        if coordinator_rate is not None and entity_count > 0
        else None
    )

    return {
        "status": status,
        "uptime_seconds": round(now - float(coordinator._runtime_perf_started), 1),
        "window_age_seconds": round(elapsed, 1),
        "entity_count": entity_count,
        "estimated_entity_writes_per_min": estimated_entity_writes,
        "current_rates_per_min": rates,
        "current_window_counts": counts,
        "last_window_seconds": round(
            float(coordinator._runtime_perf_last_window_seconds), 1
        ),
        "last_window_rates_per_min": dict(
            coordinator._runtime_perf_last_window_rates
        ),
        "last_window_counts": dict(coordinator._runtime_perf_last_window_counts),
        "totals": dict(coordinator._runtime_perf_totals),
    }


def install_performance_diagnostics() -> None:
    """Install in-memory counters after all model wrappers are in place."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__
    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data
    previous_task_events = AnthbotGenieDataUpdateCoordinator._async_refresh_task_events
    previous_set_updated_data = AnthbotGenieDataUpdateCoordinator.async_set_updated_data

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        _ensure_state(self)

    async def live_shadow(
        self: AnthbotGenieDataUpdateCoordinator,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        _record(self, "mqtt_shadow_updates")
        if shadow_name == "property":
            _record(self, "mqtt_property_updates")
        elif shadow_name == "service":
            _record(self, "mqtt_service_updates")
        await previous_live(self, shadow_name, reported)

    async def update_data(
        self: AnthbotGenieDataUpdateCoordinator,
    ) -> dict[str, Any]:
        _record(self, "coordinator_refreshes")
        return await previous_update(self)

    async def refresh_task_events(self: AnthbotGenieDataUpdateCoordinator) -> None:
        _record(self, "task_event_refresh_attempts")
        before = float(getattr(self, "_last_task_event_download_monotonic", 0.0))
        await previous_task_events(self)
        after = float(getattr(self, "_last_task_event_download_monotonic", 0.0))
        if after != before:
            _record(self, "task_event_downloads")

    def set_updated_data(
        self: AnthbotGenieDataUpdateCoordinator, data: dict[str, Any]
    ) -> None:
        _record(self, "coordinator_updates")
        if isinstance(data, dict):
            # Diagnostic-only and shallow: no map/path payload is copied.
            data["_runtime_performance"] = _snapshot(self)
        previous_set_updated_data(self, data)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
    AnthbotGenieDataUpdateCoordinator._async_refresh_task_events = refresh_task_events
    AnthbotGenieDataUpdateCoordinator.async_set_updated_data = set_updated_data
    AnthbotGenieDataUpdateCoordinator.runtime_performance_snapshot = _snapshot
    AnthbotGenieDataUpdateCoordinator.runtime_performance_record = _record

    # Count the exact M-series merged-path rebuilds identified by cProfile as a
    # potential hot path, without instrumenting every point conversion.
    from . import m_series_path

    previous_merged = m_series_path._merged

    def merged(self: AnthbotGenieDataUpdateCoordinator):
        _record(self, "path_merges")
        return previous_merged(self)

    m_series_path._merged = merged

    # Expose counters on the already-existing Map entity, rather than adding a
    # new coordinator-driven entity that would itself increase update traffic.
    from .. import sensor as sensor_platform

    previous_map_attributes = sensor_platform.AnthbotMapSensorEntity.extra_state_attributes
    sensor_platform.AnthbotMapSensorEntity._unrecorded_attributes = frozenset(
        set(sensor_platform.AnthbotMapSensorEntity._unrecorded_attributes)
        | {"runtime_performance"}
    )

    def map_attributes(self) -> dict[str, Any]:
        attributes = dict(previous_map_attributes.fget(self))
        attributes["runtime_performance"] = _snapshot(self.coordinator)
        return attributes

    sensor_platform.AnthbotMapSensorEntity.extra_state_attributes = property(map_attributes)

    # Count expensive progress evaluations at the entity boundary.  This is
    # intentionally much cheaper than instrumenting geometry helper functions.
    previous_native_value = sensor_platform.AnthbotSensorEntity.native_value
    previous_extra_attributes = sensor_platform.AnthbotSensorEntity.extra_state_attributes
    progress_keys = {"mowing_progress", "active_zone_area"}

    def native_value(self):
        if self.entity_description.key in progress_keys:
            _record(self.coordinator, "progress_sensor_evaluations")
        return previous_native_value.fget(self)

    def extra_attributes(self) -> dict[str, Any]:
        if self.entity_description.key in progress_keys:
            _record(self.coordinator, "progress_attribute_evaluations")
        return previous_extra_attributes.fget(self)

    sensor_platform.AnthbotSensorEntity.native_value = property(native_value)
    sensor_platform.AnthbotSensorEntity.extra_state_attributes = property(extra_attributes)
