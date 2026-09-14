"""Genie-only live mowing-path refresh with M-series-like presentation.

M9/M9 Pro receive live ``curpath`` chunks and replace an old task trajectory
atomically when the first chunk of the next task arrives. Genie uses a different
protocol: it uploads a complete trajectory after ``req_all_path``. This layer
keeps that proven Genie transport, but presents it with the same visual
semantics as M-series: no empty-path flash, atomic old->new task replacement,
and append-only deltas while the same task grows.

The implementation is deliberately isolated to the Genie family. M5/M9/N8
assemblers and command routes are not touched.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TYPE_CHECKING

from .base import model_family

if TYPE_CHECKING:
    from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False

# The coordinator's req_all_path helper already enforces a 10-second command
# throttle. A five-second loop reacts immediately to an already changed
# path_time without increasing the command frequency.
_LIVE_PATH_TICK_SECONDS = 5.0
_NEW_TASK_STARTUP_GRACE_SECONDS = 60.0


def _is_genie(coordinator: Any) -> bool:
    return (
        model_family(getattr(getattr(coordinator, "device", None), "model", None))
        == "genie"
    )


def _path_time(state: Any) -> str | None:
    if not isinstance(state, dict):
        return None
    value = state.get("path_time")
    return value if isinstance(value, str) and value else None


def _definition_points(value: Any) -> list[Any] | None:
    if not isinstance(value, dict):
        return None
    points = value.get("_path_points")
    return points if isinstance(points, list) else None


def _definition_has_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    points = _definition_points(value)
    if points is not None:
        return bool(points) or len(value) > 1
    return bool(value)


def _point_signature(point: Any) -> Any:
    if not isinstance(point, dict):
        return point
    return tuple(
        (key, point.get(key))
        for key in ("x", "y", "z", "yaw", "heading", "angle", "type")
        if key in point
    )


def _definition_continues(previous: Any, current: Any) -> bool:
    """Return whether a complete Genie snapshot is an extension of the old one."""
    previous_points = _definition_points(previous)
    current_points = _definition_points(current)
    if previous_points is None or current_points is None:
        return True
    if not previous_points:
        return True
    if len(current_points) < len(previous_points):
        return False
    anchor = len(previous_points) - 1
    return _point_signature(current_points[anchor]) == _point_signature(
        previous_points[anchor]
    )


def _copy_mapping(value: Any) -> Any:
    return dict(value) if isinstance(value, dict) else value


def _remember_visible_path(coordinator: Any, state: dict[str, Any]) -> None:
    """Remember the currently visible path so stale REST work cannot flash over it."""
    definition = state.get("_path_definition")
    if not isinstance(definition, dict):
        definition = getattr(coordinator, "_path_definition", None)
    coordinator._genie_path_visible_definition = _copy_mapping(definition)

    history_info = state.get("_history_path_info")
    if history_info is None:
        history_info = getattr(coordinator, "_history_path_info", None)
    coordinator._genie_path_visible_history_info = _copy_mapping(history_info)

    history_source = state.get("_history_path_source")
    if history_source is None:
        history_source = getattr(coordinator, "_history_path_source", None)
    coordinator._genie_path_visible_history_source = history_source
    coordinator._genie_path_visible_error = state.get("_path_definition_error")

    legacy: dict[str, Any] = {}
    for key in ("path", "mowed_path", "cloud_path"):
        value = state.get(key)
        if isinstance(value, list):
            legacy[key] = value
    coordinator._genie_path_visible_legacy_paths = legacy


def _sessionize_definition(coordinator: Any, definition: Any) -> Any:
    """Give path-id-less Genie snapshots a stable task identity like M-series."""
    if not isinstance(definition, dict):
        return definition
    result = dict(definition)
    if result.get("path_id") not in (None, ""):
        return result
    serial = getattr(getattr(coordinator, "client", None), "serial_number", "genie")
    session = int(getattr(coordinator, "_genie_path_render_session", 0))
    result["path_id"] = f"genie-live:{serial}:{session}"
    return result


def _apply_definition_paths(state: dict[str, Any], definition: Any) -> None:
    """Expose the same shared path aliases used by the M9/M9 Pro layer."""
    points = _definition_points(definition)
    if points is None:
        return
    state["path"] = points
    state["mowed_path"] = points
    state["cloud_path"] = points


def _begin_new_task_path_session(coordinator: Any) -> None:
    """Mark a new Genie task without flashing an empty trajectory first."""
    state = getattr(coordinator, "reported_state", {})
    state = dict(state) if isinstance(state, dict) else {}
    baseline = _path_time(state)

    _remember_visible_path(coordinator, state)
    coordinator._genie_path_session_generation = int(
        getattr(coordinator, "_genie_path_session_generation", 0)
    ) + 1
    coordinator._genie_path_render_session = int(
        getattr(coordinator, "_genie_path_render_session", 0)
    ) + 1
    coordinator._genie_path_session_baseline_time = baseline
    coordinator._genie_path_waiting_for_new_time = True
    coordinator._genie_path_session_started_monotonic = time.monotonic()

    # Permit the new task to issue req_all_path immediately even when the old
    # task requested one less than ten seconds ago. The helper resumes its
    # normal 10-second throttle after this one boundary request.
    coordinator._last_history_path_request = None
    coordinator._last_history_path_request_monotonic = 0.0


def _accept_waiting_state_if_fresh(coordinator: Any, state: Any) -> Any:
    """Atomically swap old->new path once a fresh task snapshot is complete."""
    if not isinstance(state, dict):
        return state
    if not bool(getattr(coordinator, "_genie_path_waiting_for_new_time", False)):
        return state

    baseline = getattr(coordinator, "_genie_path_session_baseline_time", None)
    current_time = _path_time(state)
    definition = state.get("_path_definition")

    if (
        current_time is not None
        and current_time != baseline
        and _definition_has_payload(definition)
    ):
        prepared = _sessionize_definition(coordinator, definition)
        result = dict(state)
        result["_path_definition"] = prepared
        _apply_definition_paths(result, prepared)
        coordinator._path_definition = prepared
        coordinator._history_path_info = result.get("_history_path_info")
        coordinator._history_path_source = result.get("_history_path_source")
        coordinator._genie_path_waiting_for_new_time = False
        coordinator._genie_path_session_baseline_time = current_time
        _remember_visible_path(coordinator, result)
        return result

    # A periodic full coordinator refresh may still finish with the previous
    # cloud object while the new task is starting. Keep the already visible old
    # path in place instead of showing either that stale response or an empty
    # intermediate frame. This is the M9/M9 Pro visual behavior we want.
    visible_definition = getattr(coordinator, "_genie_path_visible_definition", None)
    visible_info = getattr(coordinator, "_genie_path_visible_history_info", None)
    visible_source = getattr(coordinator, "_genie_path_visible_history_source", None)
    visible_error = getattr(coordinator, "_genie_path_visible_error", None)
    visible_legacy = getattr(coordinator, "_genie_path_visible_legacy_paths", {})

    coordinator._path_definition = visible_definition
    coordinator._history_path_info = visible_info
    coordinator._history_path_source = visible_source
    coordinator._last_path_time = baseline

    result = dict(state)
    if isinstance(visible_definition, dict):
        result["_path_definition"] = visible_definition
    else:
        result.pop("_path_definition", None)
    result["_history_path_info"] = visible_info
    result["_history_path_source"] = visible_source
    result["_path_definition_error"] = visible_error
    if baseline is not None:
        result["path_time"] = baseline
    if isinstance(visible_legacy, dict):
        for key, value in visible_legacy.items():
            result[key] = value
    _apply_definition_paths(result, visible_definition)
    return result


def _pending_state(coordinator: Any) -> dict[str, Any]:
    """Return current state plus not-yet-flushed MQTT property telemetry."""
    current = getattr(coordinator, "reported_state", {})
    state = dict(current) if isinstance(current, dict) else {}
    pending = getattr(coordinator, "_pending_live_property", None)
    if isinstance(pending, dict) and pending:
        state.update(pending)
    return state


def _is_live_state(state: dict[str, Any]) -> bool:
    # Imported lazily so the pure session helpers remain unit-testable without
    # importing Home Assistant.
    from ..coordinator import _is_live_position_state

    return _is_live_position_state(state)


def _ensure_live_path_task(coordinator: Any) -> None:
    if not _is_genie(coordinator):
        return
    existing = getattr(coordinator, "_genie_live_path_task", None)
    if existing is not None and not existing.done():
        return
    coordinator._genie_live_path_task = coordinator.hass.async_create_background_task(
        _async_live_path_loop(coordinator),
        f"anthbot_genie_live_path_{coordinator.client.serial_number}",
    )


async def _async_download_current_path(
    coordinator: Any,
    *,
    generation: int,
) -> bool:
    """Request/download one fresh Genie path without ancillary REST polling."""
    from ..coordinator import _find_history_info, _find_history_path_url

    lock = getattr(coordinator, "_genie_live_path_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        coordinator._genie_live_path_lock = lock

    async with lock:
        if generation != getattr(coordinator, "_genie_path_session_generation", 0):
            return False

        snapshot = getattr(coordinator, "reported_state", {})
        snapshot = dict(snapshot) if isinstance(snapshot, dict) else {}
        current_time = _path_time(snapshot)
        last_time = getattr(coordinator, "_last_path_time", None)
        waiting = bool(getattr(coordinator, "_genie_path_waiting_for_new_time", False))
        baseline = getattr(coordinator, "_genie_path_session_baseline_time", None)

        candidate_state = snapshot
        candidate_time = current_time

        # If MQTT already announced a new path_time, download immediately.
        # Otherwise ask the mower to upload its current complete path and let the
        # proven coordinator helper wait for the corresponding shadow change.
        need_request = (
            candidate_time is None
            or candidate_time == last_time
            or (waiting and candidate_time == baseline)
        )
        if need_request:
            refreshed = await coordinator._async_request_history_path(
                current_time,
                force=True,
            )
            if isinstance(refreshed, dict):
                candidate_state = refreshed
                candidate_time = _path_time(refreshed)

        if generation != getattr(coordinator, "_genie_path_session_generation", 0):
            return False

        # During a known new-task boundary never expose the old task timestamp.
        if waiting and (candidate_time is None or candidate_time == baseline):
            return False

        if (
            not waiting
            and candidate_time == last_time
            and _definition_has_payload(getattr(coordinator, "_path_definition", None))
            and getattr(coordinator, "_path_definition_error", None) is None
        ):
            return False

        live_state = getattr(coordinator, "reported_state", {})
        live_state = dict(live_state) if isinstance(live_state, dict) else {}
        service_state = live_state.get("_service_reported")
        service_state = dict(service_state) if isinstance(service_state, dict) else {}

        try:
            history_info = _find_history_info(candidate_state, service_state)
            history_url = _find_history_path_url(candidate_state, service_state)
            if history_url:
                definition = await coordinator.account_client.async_get_device_file_url(
                    history_url,
                    label="history_path",
                )
                source = "url"
            else:
                definition = await coordinator.account_client.async_get_device_path_definition(
                    coordinator.client.serial_number
                )
                source = "presigned"
        except Exception as err:  # noqa: BLE001 - retry is intentionally best effort.
            if generation != getattr(coordinator, "_genie_path_session_generation", 0):
                return False
            coordinator._path_definition_error = str(err)
            error_state = dict(getattr(coordinator, "reported_state", {}) or {})
            error_state["_path_definition_error"] = str(err)
            if waiting:
                error_state = _accept_waiting_state_if_fresh(coordinator, error_state)
            coordinator.async_set_updated_data(error_state)
            _LOGGER.debug(
                "Genie live path refresh failed for %s: %s",
                coordinator.client.serial_number,
                err,
            )
            return False

        if generation != getattr(coordinator, "_genie_path_session_generation", 0):
            return False

        previous_definition = getattr(coordinator, "_path_definition", None)
        if not waiting and not _definition_continues(previous_definition, definition):
            # App-originated tasks do not call remember_mowing_task(). Detect
            # their first discontinuous complete path just like M9 detects a
            # changed curpath stream, so path-id-less Genie data still resets.
            coordinator._genie_path_render_session = int(
                getattr(coordinator, "_genie_path_render_session", 0)
            ) + 1

        prepared = _sessionize_definition(coordinator, definition)
        coordinator._path_definition = prepared
        coordinator._history_path_info = history_info
        coordinator._history_path_source = source
        coordinator._path_definition_error = None
        coordinator._last_path_time = candidate_time
        coordinator._last_path_download_monotonic = time.monotonic()
        if waiting:
            coordinator._genie_path_waiting_for_new_time = False
            coordinator._genie_path_session_baseline_time = candidate_time

        published = dict(getattr(coordinator, "reported_state", {}) or {})
        if candidate_time is not None:
            published["path_time"] = candidate_time
        published["_path_definition"] = prepared
        published["_history_path_info"] = history_info
        published["_history_path_source"] = source
        published["_history_path_live_refresh"] = True
        published["_history_path_last_download_monotonic"] = (
            coordinator._last_path_download_monotonic
        )
        published["_path_definition_error"] = None
        _apply_definition_paths(published, prepared)
        _remember_visible_path(coordinator, published)
        coordinator.async_set_updated_data(published)
        return True


async def _async_live_path_loop(coordinator: Any) -> None:
    """Keep only the Genie path file live while a mowing task is active."""
    try:
        while _is_genie(coordinator):
            state = getattr(coordinator, "reported_state", {})
            state = dict(state) if isinstance(state, dict) else {}
            live = _is_live_state(state)
            waiting = bool(
                getattr(coordinator, "_genie_path_waiting_for_new_time", False)
            )

            if not live and not waiting:
                return
            if waiting and not live:
                started = float(
                    getattr(
                        coordinator,
                        "_genie_path_session_started_monotonic",
                        0.0,
                    )
                )
                if started and time.monotonic() - started > _NEW_TASK_STARTUP_GRACE_SECONDS:
                    return

            generation = int(
                getattr(coordinator, "_genie_path_session_generation", 0)
            )
            await _async_download_current_path(
                coordinator,
                generation=generation,
            )
            await asyncio.sleep(_LIVE_PATH_TICK_SECONDS)
    except asyncio.CancelledError:
        raise
    finally:
        if asyncio.current_task() is getattr(coordinator, "_genie_live_path_task", None):
            coordinator._genie_live_path_task = None


def install_genie_live_path_refresh() -> None:
    """Attach Genie-only M-series-like live path presentation."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from ..coordinator import AnthbotGenieDataUpdateCoordinator

    previous_init = AnthbotGenieDataUpdateCoordinator.__init__
    previous_remember = AnthbotGenieDataUpdateCoordinator.remember_mowing_task
    previous_live = AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow
    previous_update = AnthbotGenieDataUpdateCoordinator._async_update_data
    previous_stop_live = AnthbotGenieDataUpdateCoordinator.async_stop_live_shadow

    def coordinator_init(self, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        if not _is_genie(self):
            return
        self._genie_live_path_task = None
        self._genie_live_path_lock = asyncio.Lock()
        self._genie_path_session_generation = 0
        self._genie_path_render_session = 0
        self._genie_path_session_baseline_time = None
        self._genie_path_waiting_for_new_time = False
        self._genie_path_session_started_monotonic = 0.0
        self._genie_path_visible_definition = None
        self._genie_path_visible_history_info = None
        self._genie_path_visible_history_source = None
        self._genie_path_visible_error = None
        self._genie_path_visible_legacy_paths = {}

    def remember_mowing_task(self, task_type: str, data: Any = None) -> None:
        previous_remember(self, task_type, data)
        if not _is_genie(self):
            return
        _begin_new_task_path_session(self)
        _ensure_live_path_task(self)

    async def live_shadow(
        self: AnthbotGenieDataUpdateCoordinator,
        shadow_name: str,
        reported: dict[str, Any],
    ) -> None:
        await previous_live(self, shadow_name, reported)
        if not _is_genie(self):
            return
        if _is_live_state(_pending_state(self)):
            _ensure_live_path_task(self)

    async def update_data(self) -> dict[str, Any]:
        state = await previous_update(self)
        if not _is_genie(self):
            return state
        result = _accept_waiting_state_if_fresh(self, state)
        if isinstance(result, dict) and _is_live_state(result):
            _ensure_live_path_task(self)
        return result

    async def stop_live_shadow(self) -> None:
        task = getattr(self, "_genie_live_path_task", None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._genie_live_path_task = None
        await previous_stop_live(self)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
    AnthbotGenieDataUpdateCoordinator.remember_mowing_task = remember_mowing_task
    AnthbotGenieDataUpdateCoordinator._async_handle_live_shadow = live_shadow
    AnthbotGenieDataUpdateCoordinator._async_update_data = update_data
    AnthbotGenieDataUpdateCoordinator.async_stop_live_shadow = stop_live_shadow
