"""Genie-only live mowing-path session refresh.

The shared coordinator keeps ancillary REST reconciliation on a five-minute
cadence while MQTT is connected.  Genie path files are different: the mower
only uploads a fresh complete trajectory after ``req_all_path`` and the live
map must request that file repeatedly while a task is active.

This layer is intentionally isolated to the Genie family.  It clears the
previous visible trajectory when Home Assistant starts a *new* task, prevents
a slow/stale cloud response from putting that old trajectory back, and runs a
small dedicated path refresh loop while Genie is mowing.  M5/M9/N8 path
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
# throttle.  A five-second loop therefore reacts quickly to an already changed
# path_time without increasing command frequency.
_LIVE_PATH_TICK_SECONDS = 5.0
_NEW_TASK_STARTUP_GRACE_SECONDS = 60.0


def _is_genie(coordinator: Any) -> bool:
    return model_family(getattr(getattr(coordinator, "device", None), "model", None)) == "genie"


def _path_time(state: Any) -> str | None:
    if not isinstance(state, dict):
        return None
    value = state.get("path_time")
    return value if isinstance(value, str) and value else None


def _blank_path_definition() -> dict[str, list[Any]]:
    """Return an explicit empty path that cannot fall back to a stale path list."""
    return {"_path_points": []}


def _definition_has_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    points = value.get("_path_points")
    if isinstance(points, list):
        return bool(points) or len(value) > 1
    return bool(value)


def _publish_empty_new_task_path(coordinator: Any) -> None:
    """Immediately remove the previous Genie trajectory for a new HA task."""
    state = getattr(coordinator, "reported_state", {})
    state = dict(state) if isinstance(state, dict) else {}
    baseline = _path_time(state)

    coordinator._genie_path_session_generation = int(
        getattr(coordinator, "_genie_path_session_generation", 0)
    ) + 1
    coordinator._genie_path_session_baseline_time = baseline
    coordinator._genie_path_waiting_for_new_time = True
    coordinator._genie_path_session_started_monotonic = time.monotonic()

    # Reset every cached source used by live_map_stream_core path identity.
    blank = _blank_path_definition()
    coordinator._path_definition = blank
    coordinator._history_path_info = None
    coordinator._history_path_source = None
    coordinator._path_definition_error = None
    coordinator._last_path_time = baseline
    coordinator._last_path_download_monotonic = 0.0

    # Permit the new task to issue req_all_path immediately even when the old
    # task requested one less than ten seconds ago.
    coordinator._last_history_path_request = None
    coordinator._last_history_path_request_monotonic = 0.0

    state["_path_definition"] = blank
    state["_history_path_info"] = None
    state["_history_path_source"] = None
    state["_path_definition_error"] = None
    state["_history_path_live_refresh"] = True
    state["_history_path_last_download_monotonic"] = 0.0
    coordinator.async_set_updated_data(state)


def _mask_stale_path_while_waiting(coordinator: Any, state: Any) -> Any:
    """Keep the old task path hidden until the new task publishes a new path_time."""
    if not isinstance(state, dict):
        return state
    if not bool(getattr(coordinator, "_genie_path_waiting_for_new_time", False)):
        return state

    baseline = getattr(coordinator, "_genie_path_session_baseline_time", None)
    current_time = _path_time(state)
    definition = state.get("_path_definition")

    # A changed non-empty path_time plus an actual decoded payload is the point
    # at which the new session is safe to expose.  Until then a periodic
    # coordinator refresh may have re-downloaded the previous cloud object.
    if (
        current_time is not None
        and current_time != baseline
        and _definition_has_payload(definition)
    ):
        coordinator._genie_path_waiting_for_new_time = False
        coordinator._genie_path_session_baseline_time = current_time
        return state

    blank = _blank_path_definition()
    coordinator._path_definition = blank
    coordinator._history_path_info = None
    coordinator._history_path_source = None

    result = dict(state)
    result["_path_definition"] = blank
    result["_history_path_info"] = None
    result["_history_path_source"] = None
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
    # Imported lazily so the pure session helpers above remain testable without
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
    """Request/download one fresh Genie path without running ancillary REST work."""
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

        # If MQTT has already announced a new path_time, download immediately.
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

        # During a new-task boundary never accept the old task's timestamp.
        if waiting and (candidate_time is None or candidate_time == baseline):
            return False

        # A timeout with the same already-decoded path means there is nothing
        # new to download.  Errors are allowed to retry the same timestamp.
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
                error_state["_path_definition"] = _blank_path_definition()
            coordinator.async_set_updated_data(error_state)
            _LOGGER.debug(
                "Genie live path refresh failed for %s: %s",
                coordinator.client.serial_number,
                err,
            )
            return False

        if generation != getattr(coordinator, "_genie_path_session_generation", 0):
            return False

        coordinator._path_definition = definition
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
        published["_path_definition"] = definition
        published["_history_path_info"] = history_info
        published["_history_path_source"] = source
        published["_history_path_live_refresh"] = True
        published["_history_path_last_download_monotonic"] = (
            coordinator._last_path_download_monotonic
        )
        published["_path_definition_error"] = None
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
    """Attach Genie-only task reset and dedicated live path refresh behavior."""
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
        self._genie_path_session_baseline_time = None
        self._genie_path_waiting_for_new_time = False
        self._genie_path_session_started_monotonic = 0.0

    def remember_mowing_task(self, task_type: str, data: Any = None) -> None:
        previous_remember(self, task_type, data)
        if not _is_genie(self):
            return
        _publish_empty_new_task_path(self)
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
        result = _mask_stale_path_while_waiting(self, state)
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
