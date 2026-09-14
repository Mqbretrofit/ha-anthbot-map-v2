"""Resilience helpers for temporary ANTHBOT cloud/API failures.

This module deliberately stays outside mower control. It classifies temporary
vendor-cloud failures, adds bounded retries where the base API does not have
one, coalesces overlapping task-event requests, emits privacy-safe failure
signals for opt-in reporting, and rate-limits repeated Home Assistant warnings.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import re
import threading
import time
from typing import Any

from ..api import AnthbotCloudApiClient, AnthbotGenieApiError, AnthbotShadowApiClient

_LOGGER = logging.getLogger(__name__)

_TASK_EVENT_RETRY_DELAYS_SECONDS = (1, 3)
_TASK_EVENT_FAILURE_COOLDOWN_SECONDS = 5.0
_WARNING_RATE_LIMIT_SECONDS = 30 * 60
_RECENT_EVENT_REPLAY_SECONDS = 10 * 60

_API_CODE_RE = re.compile(r"\bcode=(\d{3})\b", re.IGNORECASE)
_HTTP_STATUS_RE = re.compile(r"\bfailed \((\d{3})\)", re.IGNORECASE)

_INSTALLED = False
_LISTENERS: dict[str, list[Callable[["CloudApiErrorEvent"], None]]] = {}
_RECENT_ERRORS: dict[str, "CloudApiErrorEvent"] = {}


@dataclass(frozen=True, slots=True)
class CloudApiErrorEvent:
    """Privacy-safe description of one final temporary ANTHBOT cloud failure."""

    serial_number: str
    operation: str
    api_code: int | None
    status_code: int | None
    temporary: bool
    attempts: int | None
    message: str
    occurred_monotonic: float

    @property
    def signature(self) -> tuple[str, int | None, int | None, str]:
        """Stable dedupe key that never contains credentials or raw payloads."""
        return (self.operation, self.api_code, self.status_code, self.message)


class _CloudWarningRateLimitFilter(logging.Filter):
    """Suppress repeated vendor-cloud warnings without hiding new failures."""

    _TARGET_TEXT = (
        "Unable to obtain Anthbot IoT credentials for",
        "Unable to refresh Anthbot IoT credentials for",
        "Anthbot task events unavailable for",
        "Battery saver could not refresh task events for",
    )

    def __init__(self) -> None:
        super().__init__()
        self._seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < logging.WARNING:
            return True
        message = record.getMessage()
        if not any(text in message for text in self._TARGET_TEXT):
            return True

        now = time.monotonic()
        key = (record.name, message)
        with self._lock:
            last = self._seen.get(key)
            if last is not None and now - last < _WARNING_RATE_LIMIT_SECONDS:
                return False
            self._seen[key] = now
            # Keep the small in-memory cache bounded for long-running HA hosts.
            cutoff = now - (_WARNING_RATE_LIMIT_SECONDS * 2)
            stale = [item for item, seen_at in self._seen.items() if seen_at < cutoff]
            for item in stale:
                self._seen.pop(item, None)
        return True


def _extract_api_code(message: str) -> int | None:
    match = _API_CODE_RE.search(message)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _extract_http_status(err: AnthbotGenieApiError) -> int | None:
    if isinstance(getattr(err, "status_code", None), int):
        return err.status_code
    match = _HTTP_STATUS_RE.search(str(err))
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _classify_cloud_error(err: AnthbotGenieApiError) -> AnthbotGenieApiError:
    """Mark retryable vendor responses that arrived as HTTP-200 JSON errors."""
    message = str(err)
    api_code = _extract_api_code(message)
    status_code = _extract_http_status(err)

    if api_code is not None:
        setattr(err, "api_code", api_code)
    if status_code is not None and getattr(err, "status_code", None) is None:
        err.status_code = status_code

    temporary = bool(getattr(err, "temporary", False))
    temporary = temporary or (api_code is not None and 500 <= api_code <= 599)
    temporary = temporary or (
        status_code is not None
        and (status_code == 408 or status_code == 429 or 500 <= status_code <= 599)
    )
    temporary = temporary or message.startswith("Request timed out")
    temporary = temporary or message.startswith("Network error:")
    if temporary:
        err.temporary = True
    return err


def _safe_message(err: AnthbotGenieApiError) -> str:
    """Return a report-safe summary without raw cloud response bodies."""
    api_code = getattr(err, "api_code", None)
    if isinstance(api_code, int):
        return f"ANTHBOT API returned code={api_code}"
    status_code = _extract_http_status(err)
    if isinstance(status_code, int):
        return f"ANTHBOT HTTP request failed with status={status_code}"
    text = str(err)
    if text.startswith("Request timed out"):
        return "Request timed out"
    if text.startswith("Network error:"):
        return "Network error"
    return "ANTHBOT cloud request failed"


def _build_event(
    serial_number: str,
    operation: str,
    err: AnthbotGenieApiError,
    *,
    attempts: int | None,
) -> CloudApiErrorEvent:
    err = _classify_cloud_error(err)
    return CloudApiErrorEvent(
        serial_number=serial_number,
        operation=operation,
        api_code=getattr(err, "api_code", None),
        status_code=_extract_http_status(err),
        temporary=err.is_temporary,
        attempts=attempts,
        message=_safe_message(err),
        occurred_monotonic=time.monotonic(),
    )


def _emit_cloud_error(event: CloudApiErrorEvent) -> None:
    """Publish one failure event to registered opt-in diagnostic observers."""
    _RECENT_ERRORS[event.serial_number] = event
    for callback in tuple(_LISTENERS.get(event.serial_number, ())):
        try:
            callback(event)
        except Exception:  # noqa: BLE001 - diagnostics must never break control
            _LOGGER.debug(
                "Cloud error listener failed for %s",
                event.serial_number,
                exc_info=True,
            )


def register_cloud_error_listener(
    serial_number: str,
    callback: Callable[[CloudApiErrorEvent], None],
) -> Callable[[], None]:
    """Register a privacy-safe cloud failure listener for one mower."""
    listeners = _LISTENERS.setdefault(serial_number, [])
    listeners.append(callback)

    recent = _RECENT_ERRORS.get(serial_number)
    if (
        recent is not None
        and time.monotonic() - recent.occurred_monotonic <= _RECENT_EVENT_REPLAY_SECONDS
    ):
        try:
            callback(recent)
        except Exception:  # noqa: BLE001 - reporting remains best-effort
            _LOGGER.debug(
                "Cloud error replay listener failed for %s",
                serial_number,
                exc_info=True,
            )

    def _remove() -> None:
        current = _LISTENERS.get(serial_number)
        if current is None:
            return
        try:
            current.remove(callback)
        except ValueError:
            return
        if not current:
            _LISTENERS.pop(serial_number, None)

    return _remove


def install_cloud_api_resilience() -> None:
    """Install bounded cloud retries/reporting hooks exactly once."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    original_iot_sts = AnthbotCloudApiClient.async_get_device_iot_credentials
    original_task_events = AnthbotCloudApiClient.async_get_task_events
    original_get_credentials = AnthbotShadowApiClient._async_get_credentials

    async def _iot_sts_with_classification(
        self: AnthbotCloudApiClient,
        serial_number: str,
    ) -> Any:
        try:
            result = await original_iot_sts(self, serial_number)
        except AnthbotGenieApiError as err:
            raise _classify_cloud_error(err)
        else:
            return result

    async def _task_events_with_retry(
        self: AnthbotCloudApiClient,
        serial_number: str,
        *,
        page: int = 1,
        page_size: int = 20,
        language: str = "English",
    ) -> dict[str, Any]:
        locks = getattr(self, "_anthbot_task_event_retry_locks", None)
        if not isinstance(locks, dict):
            locks = {}
            setattr(self, "_anthbot_task_event_retry_locks", locks)
        lock = locks.get(serial_number)
        if not isinstance(lock, asyncio.Lock):
            lock = asyncio.Lock()
            locks[serial_number] = lock

        async with lock:
            failures = getattr(self, "_anthbot_task_event_failures", None)
            if not isinstance(failures, dict):
                failures = {}
                setattr(self, "_anthbot_task_event_failures", failures)

            previous = failures.get(serial_number)
            if isinstance(previous, tuple) and len(previous) == 2:
                failed_at, previous_event = previous
                if (
                    isinstance(failed_at, (int, float))
                    and isinstance(previous_event, CloudApiErrorEvent)
                    and time.monotonic() - float(failed_at)
                    < _TASK_EVENT_FAILURE_COOLDOWN_SECONDS
                ):
                    cached = AnthbotGenieApiError(
                        previous_event.message,
                        status_code=previous_event.status_code,
                        temporary=True,
                    )
                    if previous_event.api_code is not None:
                        setattr(cached, "api_code", previous_event.api_code)
                    raise cached

            attempt_count = len(_TASK_EVENT_RETRY_DELAYS_SECONDS) + 1
            for attempt in range(attempt_count):
                try:
                    result = await original_task_events(
                        self,
                        serial_number,
                        page=page,
                        page_size=page_size,
                        language=language,
                    )
                except AnthbotGenieApiError as err:
                    err = _classify_cloud_error(err)
                    if not err.is_temporary or attempt >= attempt_count - 1:
                        if err.is_temporary:
                            event = _build_event(
                                serial_number,
                                "task_events",
                                err,
                                attempts=attempt + 1,
                            )
                            failures[serial_number] = (time.monotonic(), event)
                            _emit_cloud_error(event)
                        raise err
                    delay = _TASK_EVENT_RETRY_DELAYS_SECONDS[attempt]
                    _LOGGER.debug(
                        "Temporary ANTHBOT task-event cloud failure for %s "
                        "(attempt %d/%d); retrying in %d seconds: %s",
                        serial_number,
                        attempt + 1,
                        attempt_count,
                        delay,
                        err,
                    )
                    await asyncio.sleep(delay)
                else:
                    failures.pop(serial_number, None)
                    return result

            raise AnthbotGenieApiError("Task-event retry loop exhausted")

    async def _credentials_with_final_failure_reporting(
        self: AnthbotShadowApiClient,
        *,
        force_refresh: bool = False,
    ) -> Any:
        try:
            return await original_get_credentials(self, force_refresh=force_refresh)
        except AnthbotGenieApiError as err:
            err = _classify_cloud_error(err)
            if err.is_temporary:
                event = _build_event(
                    self._serial_number,
                    "iot_sts",
                    err,
                    attempts=None,
                )
                _emit_cloud_error(event)
            raise err

    AnthbotCloudApiClient.async_get_device_iot_credentials = _iot_sts_with_classification
    AnthbotCloudApiClient.async_get_task_events = _task_events_with_retry
    AnthbotShadowApiClient._async_get_credentials = _credentials_with_final_failure_reporting

    warning_filter = _CloudWarningRateLimitFilter()
    logging.getLogger("custom_components.anthbot_map.api").addFilter(warning_filter)
    logging.getLogger("custom_components.anthbot_map.coordinator").addFilter(warning_filter)
