"""Targeted runtime reliability fixes for the 2.4.6.4 maintenance release.

The integration already uses small model/runtime adapter layers.  Keep these
fixes isolated here so Genie, M-series and N8 behavior do not bleed into each
other while we address four field-proven problems:

* stale cloud task-event errors must remain history, not look active forever;
* automatic diagnostics must be edge-triggered instead of repeating hourly;
* the AWS IoT live listener must survive transport/runtime failures and rotate
  temporary credentials after repeated reconnect failures;
* M-series logical map ids and the raster id embedded in map_manager must not
  be treated as one interchangeable identifier.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import time
from typing import Any

from .. import mqtt_live
from ..coordinator import AnthbotGenieDataUpdateCoordinator
from . import m_series_legacy

_LOGGER = logging.getLogger(__name__)
_INSTALLED = False
_PLATFORM_PATCHED = False
_TASK_EVENT_FRESH_SECONDS = 15 * 60
_TASK_EVENT_FUTURE_TOLERANCE_SECONDS = 5 * 60
_CREDENTIAL_ROTATE_AFTER_FAILURES = 3


def _is_m_series(model: object) -> bool:
    value = str(model or "").upper()
    return "M5" in value or "M9" in value


def _unwrap(value: Any) -> Any:
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def _parse_event_time(event: dict[str, Any] | None) -> datetime | None:
    if not isinstance(event, dict):
        return None
    value = event.get("create_time", event.get("time", event.get("timestamp")))
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.isdigit():
        timestamp = float(raw)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _task_event_status(
    event: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return explicit history/freshness metadata for one cloud task event."""
    event_time = _parse_event_time(event)
    age_seconds: float | None = None
    if event_time is not None:
        current = now or datetime.now(timezone.utc)
        age_seconds = (current - event_time).total_seconds()
    if age_seconds is None:
        # Preserve compatibility with unusual firmware that omits/changes its
        # event timestamp shape.  Unknown age is not silently declared stale.
        fresh = True
        stale: bool | None = None
    else:
        fresh = (
            -_TASK_EVENT_FUTURE_TOLERANCE_SECONDS
            <= age_seconds
            <= _TASK_EVENT_FRESH_SECONDS
        )
        stale = not fresh
    is_error = (
        isinstance(event, dict)
        and str(event.get("code_type") or "").strip().casefold() == "error"
    )
    return {
        "is_error": is_error,
        "fresh": fresh,
        "stale": stale,
        "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
        "fresh_window_seconds": _TASK_EVENT_FRESH_SECONDS,
        "event_time": event_time.isoformat() if event_time is not None else None,
        "active_task_event_error": bool(is_error and fresh),
    }


def _fresh_error_event(event: dict[str, Any] | None) -> bool:
    status = _task_event_status(event)
    return bool(status["active_task_event_error"])


def _safe_mqtt_error(error: Exception) -> str:
    helper = getattr(mqtt_live, "_safe_error", None)
    if callable(helper):
        try:
            return str(helper(error))
        except Exception:  # noqa: BLE001 - diagnostics must never break recovery.
            pass
    return f"{type(error).__name__}: {error}"


async def _resilient_live_shadow_run(self: Any) -> None:
    """Reconnect forever unless explicitly stopped.

    The old loop covered the expected aiohttp/network exceptions but a runtime
    error from a closing MQTT transport could escape and permanently kill the
    background listener.  Field captures then kept the last live error for
    hours.  This supervisor deliberately catches normal Exceptions, keeps
    CancelledError semantics intact, and rotates STS credentials after repeated
    failed reconnects rather than hammering STS on every transient disconnect.
    """
    delay = int(getattr(mqtt_live, "_RECONNECT_INITIAL_SECONDS", 5))
    max_delay = int(getattr(mqtt_live, "_RECONNECT_MAX_SECONDS", 30))
    refresh_credentials = False

    while not self._stop.is_set():  # noqa: SLF001 - installed on listener class.
        try:
            if refresh_credentials:
                try:
                    await self._client._async_get_credentials(  # noqa: SLF001
                        force_refresh=True
                    )
                    _LOGGER.info(
                        "Anthbot live shadow rotated temporary IoT credentials for %s after repeated reconnect failures",
                        self._client.serial_number,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as refresh_err:  # noqa: BLE001
                    _LOGGER.warning(
                        "Anthbot live shadow could not refresh temporary IoT credentials for %s: %s",
                        self._client.serial_number,
                        _safe_mqtt_error(refresh_err),
                    )
                finally:
                    # The normal websocket URL builder still performs its own
                    # expiry check.  Do not force STS continuously if one cloud
                    # refresh attempt fails temporarily.
                    refresh_credentials = False

            await self._async_connected_session()  # noqa: SLF001
            delay = int(getattr(mqtt_live, "_RECONNECT_INITIAL_SECONDS", 5))
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - persistent listener supervisor.
            self._client.set_live_command_publisher(None)
            # _async_connected_session resets this counter to zero only after
            # MQTT CONNECT/SUBACK succeeded.  Therefore a failure after a good
            # session starts a fresh short retry sequence.
            if self._consecutive_failures == 0:  # noqa: SLF001
                delay = int(getattr(mqtt_live, "_RECONNECT_INITIAL_SECONDS", 5))
            self._consecutive_failures += 1  # noqa: SLF001
            if self._consecutive_failures >= _CREDENTIAL_ROTATE_AFTER_FAILURES:  # noqa: SLF001
                refresh_credentials = True

            error = (
                f"{_safe_mqtt_error(err)}; "
                "credential_lifecycle=refresh_on_expiry_and_after_reconnect_failures; "
                f"{self._client.iot_credential_diagnostics}"
            )
            log = (
                _LOGGER.warning
                if self._consecutive_failures == _CREDENTIAL_ROTATE_AFTER_FAILURES  # noqa: SLF001
                else _LOGGER.debug
            )
            log(
                "Anthbot live shadow unavailable for %s (attempt %d): %s",
                self._client.serial_number,
                self._consecutive_failures,  # noqa: SLF001
                error,
            )
            try:
                await self._on_connection(False, error)  # noqa: SLF001
            except Exception as callback_err:  # noqa: BLE001
                _LOGGER.debug(
                    "Anthbot live-shadow disconnect callback failed for %s: %s",
                    self._client.serial_number,
                    callback_err,
                )
        else:
            self._client.set_live_command_publisher(None)
            if not self._stop.is_set():  # noqa: SLF001
                try:
                    await self._on_connection(  # noqa: SLF001
                        False, "MQTT connection closed"
                    )
                except Exception as callback_err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Anthbot live-shadow close callback failed for %s: %s",
                        self._client.serial_number,
                        callback_err,
                    )

        if self._stop.is_set():  # noqa: SLF001
            break
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)  # noqa: SLF001
        except TimeoutError:
            delay = min(delay * 2, max_delay)


def _m_series_map_identity(state: dict[str, Any]) -> dict[str, str | None]:
    value = state.get("map")
    map_data = value if isinstance(value, dict) else {}

    def _text(key: str) -> str | None:
        raw = map_data.get(key)
        return None if raw in (None, "") else str(raw)

    return {
        "live_map_id": _text("map_id"),
        "area_id": _text("area_id"),
        "plan_id": _text("plan_id"),
    }


def _m_series_identity_signature(state: dict[str, Any]) -> tuple[str | None, ...]:
    identity = _m_series_map_identity(state)
    return (
        identity["live_map_id"],
        identity["area_id"],
        identity["plan_id"],
    )


def _m_series_identity_diagnostics(
    coordinator: AnthbotGenieDataUpdateCoordinator,
    state: dict[str, Any],
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostics = dict(base or {})
    identity = _m_series_map_identity(state)
    definition = getattr(coordinator, "_map_definition", None)
    raster_map_id: str | None = None
    archive_file: str | None = None
    if isinstance(definition, dict):
        raw_raster_id = definition.get("map_id")
        if raw_raster_id not in (None, ""):
            raster_map_id = str(raw_raster_id)
        source = definition.get("_download_source")
        if isinstance(source, dict) and source.get("filename") not in (None, ""):
            archive_file = str(source.get("filename"))
    source_name = str(getattr(coordinator, "_map_definition_source", "") or "")
    if archive_file is None and source_name.startswith("m_series_map_manager:"):
        archive_file = source_name.split(":", 1)[1] or None

    diagnostics.update(
        {
            "identity_model": "separate_logical_and_raster_ids",
            "live_map_id": identity["live_map_id"],
            "area_id": identity["area_id"],
            "plan_id": identity["plan_id"],
            "raster_map_id": raster_map_id,
            "archive_file": archive_file,
            "archive_naming": "serial_based",
        }
    )
    # Keep the historical diagnostics key for existing UI consumers, but make
    # its meaning explicit: this is the id embedded in the decoded raster.
    if raster_map_id is not None:
        diagnostics["map_id"] = raster_map_id
    return diagnostics


def _install_m_series_map_identity_fix() -> None:
    """Keep logical M-series ids separate from the raster/archive identity."""
    # The legacy fallback must never synthesize map_manager_<map_id>.tar.gz.
    # Field captures prove current map_manager object names are serial-based.
    def safe_legacy_candidates(property_state: dict[str, Any]) -> tuple[str, ...]:
        del property_state
        return tuple(dict.fromkeys(m_series_legacy._M_SERIES_MAP_CANDIDATES))  # noqa: SLF001

    m_series_legacy._m_series_map_candidates = safe_legacy_candidates  # noqa: SLF001

    previous_refresh = AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition

    async def refresh_map_definition(
        self: AnthbotGenieDataUpdateCoordinator,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        model = getattr(self.device, "model", None)
        if not _is_m_series(model):
            return await previous_refresh(
                self,
                property_state,
                now,
                allow_periodic=allow_periodic,
            )

        signature = _m_series_identity_signature(property_state)
        loaded_signature = getattr(
            self, "_m_series_map_manager_identity_signature", None
        )
        source = str(getattr(self, "_map_definition_source", "") or "")
        definition = getattr(self, "_map_definition", None)

        # Once the fixed serial-named map_manager archive is decoded, do not
        # compare its embedded raster id to map.map_id.  M5 field evidence
        # proves those ids belong to different protocol layers.  Re-fetch only
        # when the logical map/area/plan identity changes.
        if source.startswith("m_series_map_manager:") and isinstance(definition, dict):
            if loaded_signature is None:
                setattr(self, "_m_series_map_manager_identity_signature", signature)
                loaded_signature = signature
            if loaded_signature == signature:
                return _m_series_identity_diagnostics(
                    self,
                    property_state,
                    {
                        "preferred_source": "m_series_map_manager",
                        "active_source": source,
                        "experimental": True,
                    },
                ), False

        diagnostics, attempted = await previous_refresh(
            self,
            property_state,
            now,
            allow_periodic=allow_periodic,
        )
        source = str(getattr(self, "_map_definition_source", "") or "")
        definition = getattr(self, "_map_definition", None)
        if source.startswith("m_series_map_manager:") and isinstance(definition, dict):
            setattr(self, "_m_series_map_manager_identity_signature", signature)
            diagnostics = _m_series_identity_diagnostics(
                self,
                property_state,
                diagnostics,
            )
        return diagnostics, attempted

    AnthbotGenieDataUpdateCoordinator._async_refresh_map_definition = (
        refresh_map_definition
    )


def _install_mqtt_recovery_fix() -> None:
    mqtt_live.AnthbotLiveShadowListener.async_run = _resilient_live_shadow_run


def _patch_platform_modules() -> None:
    """Patch platform-level diagnostics after commands finished importing."""
    global _PLATFORM_PATCHED
    if _PLATFORM_PATCHED:
        return
    _PLATFORM_PATCHED = True

    # Import lazily: button imports commands, and commands imports the model
    # installer.  Importing button while commands is still being defined would
    # create a circular import.  Coordinator construction occurs later, after
    # the integration module graph is fully loaded and before platform setup.
    from .. import button as button_module
    from .. import firmware_diagnostics
    from .. import robot_error_reporting
    from .. import sensor as sensor_module

    original_build_report = firmware_diagnostics.build_firmware_diagnostics_report

    def build_report_with_event_status(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = original_build_report(*args, **kwargs)
        event = report.get("latest_task_event")
        report["latest_task_event_status"] = _task_event_status(
            event if isinstance(event, dict) else None
        )
        return report

    firmware_diagnostics.build_firmware_diagnostics_report = build_report_with_event_status
    # These modules imported the builder directly, so update their module-local
    # references too.
    button_module.build_firmware_diagnostics_report = build_report_with_event_status
    robot_error_reporting.build_firmware_diagnostics_report = build_report_with_event_status

    # A historical cloud error is useful context, but it is not an active
    # fault indefinitely.  Only a fresh error task-event can independently
    # trigger the dedicated robot error reporter.  A live non-zero err_code
    # continues to trigger regardless of cloud-event age.
    robot_error_reporting._is_error_event = _fresh_error_event  # noqa: SLF001

    original_attributes = sensor_module.AnthbotSensorEntity.extra_state_attributes.fget
    if original_attributes is not None:
        def extra_state_attributes(self: Any) -> dict[str, Any]:
            attributes = original_attributes(self)
            if self.entity_description.key.startswith("cloud_task_event_"):
                payload = self.coordinator.reported_state.get("_task_events")
                event = sensor_module.latest_task_event(payload)
                status = _task_event_status(event)
                attributes["latest_task_event_status"] = status
                attributes["latest_task_event_stale"] = status["stale"]
                attributes["latest_task_event_age_seconds"] = status["age_seconds"]
            return attributes

        sensor_module.AnthbotSensorEntity.extra_state_attributes = property(
            extra_state_attributes
        )

    def install_edge_triggered_automatic_diagnostics(
        hass: Any,
        entry: Any,
        coordinator: AnthbotGenieDataUpdateCoordinator,
    ) -> None:
        """Send each persistent diagnostic condition once per episode.

        Seed the currently visible condition so Home Assistant/integration
        restarts do not replay an old no-go/map/live error.  Once the condition
        clears, the same signature is eligible again if it genuinely recurs.
        """
        initial_state = coordinator.reported_state
        initial = (
            button_module._automatic_diagnostics_trigger(initial_state)  # noqa: SLF001
            if isinstance(initial_state, dict)
            else None
        )
        active_signature: str | None = initial[1] if initial is not None else None

        def handle_update() -> None:
            nonlocal active_signature
            if not button_module._entry_option_enabled(  # noqa: SLF001
                entry,
                button_module.CONF_SEND_AUTOMATIC_DIAGNOSTICS,
            ):
                return
            installation_id = entry.data.get(
                button_module.CONF_DEVELOPER_INSTALLATION_ID
            )
            if not isinstance(installation_id, str) or not installation_id:
                return
            state = coordinator.reported_state
            if not isinstance(state, dict):
                return
            detected = button_module._automatic_diagnostics_trigger(state)  # noqa: SLF001
            if detected is None:
                active_signature = None
                return
            trigger, signature = detected

            # Active mower errors have their own episode-aware reporter in
            # robot_error_reporting.py.  Do not create a second copy here.
            if trigger == "mower_error_code":
                active_signature = signature
                return
            if signature == active_signature:
                return
            active_signature = signature

            report = build_report_with_event_status(
                coordinator,
                include_raw_state=False,
                include_identifiers=False,
            )
            session = button_module.async_get_clientsession(hass)
            hass.async_create_task(
                button_module.async_send_diagnostics_report(
                    session,
                    button_module.DEVELOPER_DIAGNOSTICS_ENDPOINT,
                    installation_id=installation_id,
                    report=report,
                    trigger=trigger,
                )
            )

        unsubscribe = coordinator.async_add_listener(handle_update)
        entry.async_on_unload(unsubscribe)

    button_module._install_automatic_diagnostics_reporting = (  # noqa: SLF001
        install_edge_triggered_automatic_diagnostics
    )


def _install_deferred_platform_patch() -> None:
    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: Any, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        _patch_platform_modules()

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init


def install_runtime_reliability_fixes() -> None:
    """Install all 2.4.6.4 fixes once, after model adapters are in place."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _install_mqtt_recovery_fix()
    _install_m_series_map_identity_fix()
    _install_deferred_platform_patch()
