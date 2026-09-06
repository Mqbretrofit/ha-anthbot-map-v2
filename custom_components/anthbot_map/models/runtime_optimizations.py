"""Low-risk runtime optimizations for MQTT, task events, progress and M-series paths.

The goal is to remove repeated work without slowing real telemetry changes.  No
polling interval is increased and no mower command is delayed by this module.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..coordinator import AnthbotGenieDataUpdateCoordinator
from ..task_events import latest_task_cycle_signal
from . import live_task_events, m_series_path

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_DIAGNOSTICS_INSTALLED = False
_MISSING = object()

_ACTIVE_PHASE_STATUSES = {
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "bordermowing",
    "regionmowing",
    "nestmowing",
    "mowing",
    "working",
    "cutting",
    "edgecutting",
    "gototarget",
    "remotectrl",
}
_RETURNING_PHASE_STATUSES = {"backtodock", "returning", "returningtodock"}
_INACTIVE_PHASE_STATUSES = {
    "charge",
    "charging",
    "chargestart",
    "docked",
    "idle",
    "pause",
    "paused",
    "sleep",
    "standby",
    "shutdown",
}


def _record_optimization(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    key: str,
    amount: int = 1,
) -> None:
    """Keep tiny per-mower totals without causing an HA state write."""
    attr = f"_runtime_opt_{key}"
    current = getattr(coordinator, attr, 0)
    try:
        current = int(current)
    except (TypeError, ValueError):
        current = 0
    setattr(coordinator, attr, current + int(amount))


def _task_phase(status: str | None) -> str:
    value = str(status or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    if value in _ACTIVE_PHASE_STATUSES:
        return "active"
    if value in _RETURNING_PHASE_STATUSES:
        return "returning"
    if value in _INACTIVE_PHASE_STATUSES:
        return "inactive"
    return f"other:{value}" if value else "unknown"


def _event_signal_matches_phase(signal: str | None, current_phase: str) -> bool:
    if current_phase == "active":
        return signal == "active"
    if current_phase in {"returning", "inactive"}:
        return signal in {"completed", "low_battery_return", "rain_return"}
    return False


def _install_task_event_coalescing() -> None:
    """Ignore cosmetic status chatter and retry REST only when propagation lags."""

    def schedule_task_event_refresh(
        self: AnthbotGenieDataUpdateCoordinator,
        previous_status: str,
        current_status: str,
    ) -> None:
        previous_phase = _task_phase(previous_status)
        current_phase = _task_phase(current_status)

        # Charge/idle/sleep/standby chatter is not a task-cycle transition.
        if previous_phase == current_phase:
            return
        if not ({previous_phase, current_phase} & {"active", "returning"}):
            return

        active = getattr(self, "_live_task_event_refresh_task", None)
        if active is not None and not active.done():
            return

        async def runner() -> None:
            try:
                # A genuine task transition must bypass the ordinary five-second
                # ancillary throttle for its first event-list request.
                self._last_task_event_download_monotonic = 0.0
                await self._async_refresh_task_events()
                signal = latest_task_cycle_signal(self._task_events)
                if _event_signal_matches_phase(signal, current_phase):
                    return

                # Retry once only when the REST event list has not caught up yet.
                _record_optimization(self, "task_event_retries")
                await asyncio.sleep(live_task_events._EVENT_RETRY_SECONDS)
                await self._async_refresh_task_events()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - telemetry must keep running.
                _LOGGER.warning(
                    "Task-event refresh after live status change failed for %s "
                    "(%s -> %s): %s",
                    self.client.serial_number,
                    previous_status,
                    current_status,
                    err,
                )
            finally:
                if asyncio.current_task() is getattr(
                    self, "_live_task_event_refresh_task", None
                ):
                    self._live_task_event_refresh_task = None

        self._live_task_event_refresh_task = self.hass.async_create_background_task(
            runner(),
            f"anthbot_task_events_after_status_{self.client.serial_number}",
        )

    # The already-installed live wrapper resolves this module global at call time.
    live_task_events._schedule_task_event_refresh = schedule_task_event_refresh


def _changed_shadow_fragment(
    self: AnthbotGenieDataUpdateCoordinator,
    shadow_name: str,
    reported: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    """Drop fields that are byte-for-byte/equality identical to current+pending data."""
    if not isinstance(reported, dict) or not reported:
        return {}, 0

    state = self.reported_state
    if shadow_name == "service":
        service = state.get("_service_reported")
        baseline = dict(service) if isinstance(service, dict) else {}
        pending = getattr(self, "_pending_live_service", None)
    else:
        baseline = dict(state)
        pending = getattr(self, "_pending_live_property", None)

    if isinstance(pending, dict) and pending:
        baseline.update(pending)

    changed: dict[str, Any] = {}
    for key, value in reported.items():
        existing = baseline.get(key, _MISSING)
        if existing is _MISSING or existing != value:
            changed[key] = value
    return changed, len(reported) - len(changed)


def _install_duplicate_shadow_filter() -> None:
    """Avoid scheduling a one-second HA fan-out for repeated identical shadows."""
    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow

    async def live_shadow(
        self: AnthbotGenieDataUpdateCoordinator,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        changed, dropped = _changed_shadow_fragment(self, shadow_name, reported)
        if dropped:
            _record_optimization(self, "duplicate_mqtt_fields_dropped", dropped)
        if not changed:
            _record_optimization(self, "duplicate_mqtt_messages_suppressed")
            return
        await previous_live(self, shadow_name, changed)

    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow


def _path_merge_signature(self: AnthbotGenieDataUpdateCoordinator) -> tuple[Any, ...]:
    indexed = getattr(self, "_m_series_test4_points", None)
    template = getattr(self, "_m_series_test4_template", None)
    if not isinstance(indexed, dict):
        indexed = {}
    if not isinstance(template, dict):
        template = {}

    metadata = tuple(
        repr(template.get(key))
        for key in (
            "task_type",
            "coordinate_scale",
            "map_id",
            "area_id",
            "start",
            "path_start",
            "declared_size",
            "point_count",
        )
    )
    return (
        id(indexed),
        len(indexed),
        getattr(self, "_m_series_test4_path_id", None),
        getattr(self, "_m_series_test4_latest_angle_index", -1),
        getattr(self, "_m_series_test4_latest_angle", None),
        metadata,
    )


def _install_m_series_path_cache() -> None:
    """Reuse an assembled M-series path until points/angle/metadata really change."""
    previous_merged = m_series_path._merged

    def merged(self: AnthbotGenieDataUpdateCoordinator):
        signature = _path_merge_signature(self)
        if getattr(self, "_runtime_path_merge_cache_signature", _MISSING) == signature:
            _record_optimization(self, "path_merge_cache_hits")
            return getattr(self, "_runtime_path_merge_cache_value", None)

        result = previous_merged(self)
        if isinstance(result, dict):
            # UI caches are valid only for the exact _path_points list produced
            # by this merge; never inherit one through a copied template.
            result.pop("_runtime_ui_path_cache", None)
        self._runtime_path_merge_cache_signature = signature
        self._runtime_path_merge_cache_value = result
        return result

    m_series_path._merged = merged


def _hashable_scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return repr(value)


def _install_progress_geometry_cache() -> None:
    """Compute expensive zone/no-go geometry once per unchanged HA state geometry."""
    from .. import sensor as sensor_platform

    previous_geometry = sensor_platform._progress_active_zone_debug
    previous_learning = sensor_platform._progress_learning_debug

    def geometry_signature(data: dict[str, Any]) -> tuple[Any, ...]:
        return (
            id(data.get("_area_definition")),
            id(data.get("area_definition")),
            id(data.get("custom_areas")),
            id(data.get("_map_definition")),
            _hashable_scalar(data.get("area_time")),
            _hashable_scalar(data.get("map_area")),
            tuple(sensor_platform.active_manual_zone_ids(data)),
        )

    def progress_geometry(data: dict[str, Any]) -> dict[str, Any]:
        signature = geometry_signature(data)
        cache = data.get("_runtime_progress_geometry_cache")
        if isinstance(cache, dict) and cache.get("signature") == signature:
            data["_runtime_progress_geometry_cache_hits"] = int(
                data.get("_runtime_progress_geometry_cache_hits", 0) or 0
            ) + 1
            value = cache.get("value")
            if isinstance(value, dict):
                return value

        value = previous_geometry(data)
        data["_runtime_progress_geometry_rebuilds"] = int(
            data.get("_runtime_progress_geometry_rebuilds", 0) or 0
        ) + 1
        data["_runtime_progress_geometry_cache"] = {
            "signature": signature,
            "value": value,
        }
        return value

    def progress_learning(data: dict[str, Any]) -> dict[str, Any]:
        signature = (
            id(data.get("_mowing_area_learning")),
            tuple(sensor_platform.active_manual_zone_ids(data)),
        )
        cache = data.get("_runtime_progress_learning_cache")
        if isinstance(cache, dict) and cache.get("signature") == signature:
            value = cache.get("value")
            if isinstance(value, dict):
                return value
        value = previous_learning(data)
        data["_runtime_progress_learning_cache"] = {
            "signature": signature,
            "value": value,
        }
        return value

    sensor_platform._progress_active_zone_debug = progress_geometry
    sensor_platform._progress_learning_debug = progress_learning


def _install_map_path_view_cache() -> None:
    """Stop rebuilding/copying a large path list for every Map entity write."""
    from .. import sensor as sensor_platform

    previous_status = sensor_platform._definition_status

    def path_cache(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        points = value.get("_path_points")
        if not isinstance(points, list):
            return None
        signature = (id(points), len(points))
        cache = value.get("_runtime_ui_path_cache")
        if isinstance(cache, dict) and cache.get("signature") == signature:
            return cache

        if all(isinstance(point, dict) for point in points):
            view = points
        else:
            view = [point for point in points if isinstance(point, dict)]
        counts: dict[str, int] = {}
        for point in view:
            point_type = str(point.get("type", "missing"))
            counts[point_type] = counts.get(point_type, 0) + 1
        cache = {
            "signature": signature,
            "points": view,
            "type_counts": counts,
        }
        value["_runtime_ui_path_cache"] = cache
        return cache

    def definition_path_points(value: Any) -> list[dict[str, Any]]:
        cache = path_cache(value)
        if cache is None:
            return []
        points = cache.get("points")
        return points if isinstance(points, list) else []

    def definition_path_type_counts(value: Any) -> dict[str, int]:
        cache = path_cache(value)
        if cache is None:
            return {}
        counts = cache.get("type_counts")
        return counts if isinstance(counts, dict) else {}

    def definition_status(value: Any) -> str:
        # Keep the pre-optimization diagnostic stable even though one internal
        # cache key lives on the definition object.
        if isinstance(value, dict) and "_runtime_ui_path_cache" in value:
            return f"dict:{max(0, len(value) - 1)}"
        return previous_status(value)

    sensor_platform._definition_path_points = definition_path_points
    sensor_platform._definition_path_type_counts = definition_path_type_counts
    sensor_platform._definition_status = definition_status


def install_runtime_optimizations() -> None:
    """Install behavior-preserving runtime work suppression."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    _install_task_event_coalescing()
    _install_duplicate_shadow_filter()
    _install_m_series_path_cache()
    _install_progress_geometry_cache()
    _install_map_path_view_cache()


def _optimization_snapshot(
    coordinator: AnthbotGenieDataUpdateCoordinator,
) -> dict[str, Any]:
    totals = {
        key: int(getattr(coordinator, f"_runtime_opt_{key}", 0) or 0)
        for key in (
            "duplicate_mqtt_messages_suppressed",
            "duplicate_mqtt_fields_dropped",
            "task_event_retries",
            "path_merge_cache_hits",
        )
    }
    state = coordinator.reported_state
    totals["progress_geometry_cache_hits"] = int(
        state.get("_runtime_progress_geometry_cache_hits", 0) or 0
    )
    totals["progress_geometry_rebuilds"] = int(
        state.get("_runtime_progress_geometry_rebuilds", 0) or 0
    )

    started = float(getattr(coordinator, "_runtime_perf_started", 0.0) or 0.0)
    if started > 0:
        import time

        elapsed = max(1.0, time.monotonic() - started)
        rates = {key: round(value * 60.0 / elapsed, 2) for key, value in totals.items()}
    else:
        rates = {key: None for key in totals}
    return {"totals": totals, "rates_per_min": rates}


def install_runtime_optimization_diagnostics() -> None:
    """Append optimization effectiveness to beta.1 runtime diagnostics."""
    global _DIAGNOSTICS_INSTALLED
    if _DIAGNOSTICS_INSTALLED:
        return
    _DIAGNOSTICS_INSTALLED = True

    from . import performance_diagnostics

    previous_snapshot = performance_diagnostics._snapshot

    def snapshot(coordinator: AnthbotGenieDataUpdateCoordinator) -> dict[str, Any]:
        result = previous_snapshot(coordinator)
        result["optimization"] = _optimization_snapshot(coordinator)
        return result

    performance_diagnostics._snapshot = snapshot
