"""Dedicated WebSocket transport for ANTHBOT live map data.

The coordinator remains the single source of truth, but high-frequency path and
pose data is delivered directly to the Lovelace card instead of forcing every
live update through Home Assistant's entity state machine and Recorder.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time
from typing import Any, Callable

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .live_map_stream_core import PROTOCOL_VERSION, LiveMapCursor, build_delta, build_snapshot
from .task_events import task_event_items

_LOGGER = logging.getLogger(__name__)

LIVE_DATA_KEY = f"{DOMAIN}_live_map_stream"
LIVE_RESOURCE_PATH = "/anthbot-map-v2/live-map-stream.js"
LIVE_RESOURCE_URL = f"{LIVE_RESOURCE_PATH}?v=247-live2-1"
_COMPACT_HEARTBEAT_SECONDS = 60.0
_COMPACTION_INSTALLED = False


@dataclass
class _Subscriber:
    connection: Any
    msg_id: int
    cursor: LiveMapCursor | None = None
    sequence: int = 0
    ready: bool = False
    closed: bool = False


class LiveMapHub:
    """Fan out one mower coordinator to independent WebSocket subscribers."""

    def __init__(self, hass: HomeAssistant, coordinator: Any) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.serial_number = coordinator.client.serial_number
        self._subscribers: dict[tuple[int, int], _Subscriber] = {}
        self._remove_listener: Callable[[], None] | None = coordinator.async_add_listener(
            self._handle_coordinator_update
        )
        self._closed = False

    def subscribe_pending(
        self,
        connection: Any,
        msg_id: int,
    ) -> tuple[_Subscriber, Callable[[], None]]:
        """Register a subscriber before the browser can observe WS success."""
        key = (id(connection), msg_id)
        previous = self._subscribers.pop(key, None)
        if previous is not None:
            previous.closed = True

        subscriber = _Subscriber(connection=connection, msg_id=msg_id)
        self._subscribers[key] = subscriber

        def unsubscribe() -> None:
            current = self._subscribers.pop(key, None)
            if current is not None:
                current.closed = True

        return subscriber, unsubscribe

    async def async_prepare_snapshot(
        self,
        subscriber: _Subscriber,
    ) -> tuple[dict[str, Any], LiveMapCursor] | None:
        """Prepare the initial frame without emitting a WebSocket event yet."""
        if self._closed or subscriber.closed:
            return None

        # Snapshot construction can touch a 20k-point trajectory. Keep that
        # one-time work out of Home Assistant's event loop. Coordinator state
        # objects are replaced on update; a shallow top-level snapshot keeps
        # the reference set coherent for this short executor job.
        state_snapshot = dict(self.coordinator.reported_state)
        payload, cursor = await self.hass.async_add_executor_job(
            build_snapshot,
            self.serial_number,
            0,
            state_snapshot,
        )
        if self._closed or subscriber.closed:
            return None
        return payload, cursor

    def activate_subscriber(
        self,
        subscriber: _Subscriber,
        payload: dict[str, Any],
        cursor: LiveMapCursor,
    ) -> None:
        """Emit snapshot after WS success and close the snapshot/update race."""
        if self._closed or subscriber.closed:
            return
        subscriber.cursor = cursor
        subscriber.sequence = 0
        subscriber.ready = True
        self._send_event(subscriber, payload)

        # A coordinator update may have arrived while the initial snapshot was
        # built. Emit one continuity-checked catch-up delta immediately.
        self._send_current_delta(subscriber)

    def _send_event(self, subscriber: _Subscriber, payload: dict[str, Any]) -> None:
        try:
            subscriber.connection.send_event(subscriber.msg_id, payload)
        except Exception:  # noqa: BLE001 - a dead browser must not affect HA.
            _LOGGER.debug(
                "ANTHBOT live map subscriber send failed for %s",
                self.serial_number,
                exc_info=True,
            )

    def _send_current_delta(self, subscriber: _Subscriber) -> None:
        if not subscriber.ready or subscriber.closed or subscriber.cursor is None:
            return
        next_sequence = subscriber.sequence + 1
        payload, cursor = build_delta(
            self.serial_number,
            next_sequence,
            subscriber.cursor,
            self.coordinator.reported_state,
        )
        subscriber.cursor = cursor
        if payload is None:
            return
        subscriber.sequence = next_sequence
        self._send_event(subscriber, payload)

    def _handle_coordinator_update(self) -> None:
        if self._closed or not self._subscribers:
            return
        for subscriber in tuple(self._subscribers.values()):
            self._send_current_delta(subscriber)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        for subscriber in self._subscribers.values():
            subscriber.closed = True
        self._subscribers.clear()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "anthbot_map/subscribe_live",
        vol.Required("serial_number"): str,
    }
)
@websocket_api.async_response
async def _websocket_subscribe_live(
    hass: HomeAssistant,
    connection: Any,
    msg: dict[str, Any],
) -> None:
    """Subscribe one card to a mower's dedicated live map stream."""
    data = hass.data.get(LIVE_DATA_KEY, {})
    hubs = data.get("hubs", {}) if isinstance(data, dict) else {}
    hub = hubs.get(msg["serial_number"]) if isinstance(hubs, dict) else None
    if not isinstance(hub, LiveMapHub):
        connection.send_error(
            msg["id"],
            "not_found",
            f"ANTHBOT mower {msg['serial_number']} is not available",
        )
        return

    # Register the cleanup callback *before* the browser can see a successful
    # subscription. This avoids leaking a subscriber if the card disconnects
    # while its initial (potentially large) snapshot is being prepared.
    subscriber, unsubscribe = hub.subscribe_pending(connection, msg["id"])
    connection.subscriptions[msg["id"]] = unsubscribe
    try:
        prepared = await hub.async_prepare_snapshot(subscriber)
    except Exception as err:  # noqa: BLE001 - keep one card failure isolated.
        unsubscribe()
        connection.subscriptions.pop(msg["id"], None)
        _LOGGER.exception(
            "Unable to prepare ANTHBOT live map snapshot for %s",
            msg["serial_number"],
        )
        connection.send_error(msg["id"], "snapshot_failed", str(err))
        return

    if prepared is None:
        # The connection or hub was closed while executor work was in flight.
        unsubscribe()
        connection.subscriptions.pop(msg["id"], None)
        return

    payload, cursor = prepared
    connection.send_result(msg["id"])
    hub.activate_subscriber(subscriber, payload, cursor)


async def _async_ensure_frontend_resource(hass: HomeAssistant) -> bool:
    """Register the live-stream patch resource when Lovelace storage is writable."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None or getattr(lovelace, "resource_mode", None) != MODE_STORAGE:
        _LOGGER.info(
            "ANTHBOT live map stream stays in compatibility mode because Lovelace "
            "resources are not stored in UI storage mode"
        )
        return False

    resources = getattr(lovelace, "resources", None)
    if resources is None:
        _LOGGER.warning(
            "ANTHBOT live map stream stays in compatibility mode because Lovelace "
            "resource storage is unavailable"
        )
        return False

    try:
        await resources.async_get_info()
        matching = [
            item
            for item in resources.async_items()
            if str(item.get("url", "")).split("?", 1)[0] == LIVE_RESOURCE_PATH
        ]
        if matching:
            current = matching[0]
            if current.get("url") != LIVE_RESOURCE_URL or current.get("type") != "module":
                await resources.async_update_item(
                    current["id"],
                    {"res_type": "module", "url": LIVE_RESOURCE_URL},
                )
            if len(matching) > 1:
                _LOGGER.warning(
                    "Multiple ANTHBOT live-map resources exist; keeping duplicates "
                    "unchanged except for the first entry"
                )
            return True

        await resources.async_create_item(
            {"res_type": "module", "url": LIVE_RESOURCE_URL}
        )
        return True
    except Exception:  # noqa: BLE001 - fallback entity path must remain usable.
        _LOGGER.exception(
            "Unable to register ANTHBOT live-map resource; keeping full Map entity "
            "attributes for compatibility"
        )
        return False


def _cheap_preview(value: Any) -> Any:
    if isinstance(value, dict):
        return {"keys": [str(key) for key in list(value.keys())[:20]]}
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    return None


def _compact_path_metadata(state: dict[str, Any]) -> dict[str, Any]:
    definition = state.get("_path_definition")
    if not isinstance(definition, dict):
        return {
            "path_id": None,
            "path_start": None,
            "path_task_type": None,
            "path_point_count": 0,
            "path_coordinate_scale": None,
            "path_first_point": None,
            "path_window_first_index": None,
            "path_window_last_index": None,
        }
    points = definition.get("_path_points")
    if not isinstance(points, list):
        points = state.get("path") if isinstance(state.get("path"), list) else []
    return {
        "path_id": definition.get("path_id"),
        "path_start": definition.get("start"),
        "path_task_type": definition.get("task_type"),
        "path_point_count": len(points),
        "path_coordinate_scale": definition.get("coordinate_scale"),
        "path_first_point": points[0] if points and isinstance(points[0], dict) else None,
        "path_window_first_index": definition.get("_m_series_first_index"),
        "path_window_last_index": definition.get("_m_series_last_index"),
    }


def _compact_extra_state_attributes(sensor_module: Any, entity: Any) -> dict[str, Any]:
    """Return Recorder-safe Map metadata without live geometry payloads."""
    state = entity.coordinator.reported_state
    map_definition = state.get("_map_definition")
    path_definition = state.get("_path_definition")
    attributes: dict[str, Any] = {
        "serial_number": entity.coordinator.client.serial_number,
        "model": entity.coordinator.device.model,
        "mower_status": sensor_module._general_mower_status(state),  # noqa: SLF001
        "robot_status_raw": sensor_module._raw_robot_status(state),  # noqa: SLF001
        "live_stream_available": True,
        "live_stream_version": PROTOCOL_VERSION,
        "live_stream_transport": "websocket",
        "map_time": state.get("map_time"),
        "path_time": state.get("path_time"),
        "area_time": state.get("area_time"),
        "ridable_area_time": state.get("ridable_area_time"),
        "history_path_info": state.get("_history_path_info"),
        "history_path_source": state.get("_history_path_source"),
        "history_path_live_refresh": state.get("_history_path_live_refresh"),
        "history_path_refresh_interval": state.get("_history_path_refresh_interval"),
        "history_path_download_source": (
            path_definition.get("_download_source")
            if isinstance(path_definition, dict)
            else None
        ),
        "ridable_area_error": state.get("_ridable_area_definition_error"),
        "map_definition_status": sensor_module._definition_status(map_definition),  # noqa: SLF001
        "path_definition_status": sensor_module._definition_status(path_definition),  # noqa: SLF001
        "map_definition_preview": _cheap_preview(map_definition),
        "map_archive_selection": state.get("_map_archive_selection"),
        "path_definition_preview": _cheap_preview(path_definition),
        "map_definition_error": state.get("_map_definition_error"),
        "path_definition_error": state.get("_path_definition_error"),
        "cloud_connected": state.get("_cloud_connected"),
        "cloud_last_success": state.get("_cloud_last_success"),
        "cloud_error": state.get("_cloud_error"),
        "robot_online": state.get("_robot_online"),
        "live_shadow_connected": state.get("_live_shadow_connected", False),
        "live_shadow_error": state.get("_live_shadow_error"),
        "last_mowing_task": entity.coordinator.last_mowing_task,
        "custom_button_actions_configured": entity.coordinator.custom_button_actions_configured,
        "custom_button_actions_enabled": entity.coordinator.custom_button_actions_enabled,
        "custom_button_actions": entity.coordinator.custom_button_actions,
        "mowing_records": state.get("_mowing_records", {"data": []}),
        "mowing_records_error": state.get("_mowing_records_error"),
        "task_events": task_event_items(state.get("_task_events")),
        "task_events_error": state.get("_task_events_error"),
        "error_history": state.get("_error_history", []),
        "maintenance": state.get("robot_maintenance")
        or {
            "blade": state.get("cutting_components_life"),
            "camera": state.get("camera_life"),
            "charging_contact": state.get("recharge_contact_life"),
        },
        # Keep diagnostics visible, but the compact write signature below does
        # not react to this high-frequency value.
        "runtime_performance": state.get("_runtime_performance"),
    }
    attributes.update(_compact_path_metadata(state))
    return attributes


def _compact_write_signature(sensor_module: Any, coordinator: Any) -> tuple[Any, ...]:
    """Track only semantic HA-state changes, never live pose/path movement."""
    from .models import recorder_idle_semantics_v2467 as idle
    from .models import recorder_v2467 as recorder

    state = coordinator.reported_state
    return (
        sensor_module._general_mower_status(state),  # noqa: SLF001
        sensor_module._raw_robot_status(state),  # noqa: SLF001
        recorder._map_definition_signature(state.get("_map_definition")),  # noqa: SLF001
        recorder._stable_small(state.get("area_time")),  # noqa: SLF001
        recorder._stable_small(state.get("ridable_area_time")),  # noqa: SLF001
        recorder._area_definition_signature(state.get("_area_definition")),  # noqa: SLF001
        recorder._area_definition_signature(  # noqa: SLF001
            state.get("_ridable_area_definition")
        ),
        idle._archive_identity(state.get("_map_archive_selection")),  # noqa: SLF001
        recorder._stable_small(state.get("_map_definition_error")),  # noqa: SLF001
        recorder._stable_small(state.get("_path_definition_error")),  # noqa: SLF001
        recorder._stable_small(state.get("_ridable_area_definition_error")),  # noqa: SLF001
        bool(state.get("_cloud_connected")),
        bool(state.get("_robot_online")),
        bool(state.get("_live_shadow_connected", False)),
        recorder._stable_small(state.get("_cloud_error")),  # noqa: SLF001
        recorder._stable_small(state.get("_live_shadow_error")),  # noqa: SLF001
        recorder._sequence_edge_signature(state.get("_mowing_records")),  # noqa: SLF001
        recorder._sequence_edge_signature(state.get("_task_events")),  # noqa: SLF001
        idle._actual_error_history_signature(state.get("_error_history")),  # noqa: SLF001
        recorder._stable_small(state.get("robot_maintenance")),  # noqa: SLF001
        recorder._stable_small(coordinator.last_mowing_task),  # noqa: SLF001
        bool(coordinator.custom_button_actions_configured),
        bool(coordinator.custom_button_actions_enabled),
        recorder._stable_small(coordinator.custom_button_actions),  # noqa: SLF001
    )


def _install_compact_map_entity() -> None:
    """Detach heavy live geometry from the Home Assistant Map entity."""
    global _COMPACTION_INSTALLED
    if _COMPACTION_INSTALLED:
        return

    from . import sensor as sensor_module

    map_entity = sensor_module.AnthbotMapSensorEntity
    previous_update = map_entity._handle_coordinator_update

    def extra_state_attributes(self: Any) -> dict[str, Any]:
        return _compact_extra_state_attributes(sensor_module, self)

    def handle_coordinator_update(self: Any) -> None:
        now = time.monotonic()
        signature = _compact_write_signature(sensor_module, self.coordinator)
        previous_signature = getattr(self, "_anthbot_live_stream_entity_signature", None)
        last_actual_write = float(
            getattr(self, "_anthbot_last_map_state_write", 0.0) or 0.0
        )
        changed = previous_signature is None or signature != previous_signature
        heartbeat_due = (
            not last_actual_write
            or now - last_actual_write >= _COMPACT_HEARTBEAT_SECONDS
        )
        if not changed and not heartbeat_due:
            return

        before_write = last_actual_write
        previous_update(self)
        after_write = float(
            getattr(self, "_anthbot_last_map_state_write", 0.0) or 0.0
        )
        if after_write != before_write:
            self._anthbot_live_stream_entity_signature = signature

    map_entity.extra_state_attributes = property(extra_state_attributes)
    map_entity._handle_coordinator_update = handle_coordinator_update
    _COMPACTION_INSTALLED = True
    _LOGGER.info(
        "ANTHBOT live map stream: Map entity geometry detached from HA state; "
        "WebSocket protocol v%s active",
        PROTOCOL_VERSION,
    )


async def async_setup_live_map_stream(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinators: list[Any],
) -> None:
    """Set up WebSocket live-map hubs for one config entry."""
    data = hass.data.setdefault(
        LIVE_DATA_KEY,
        {
            "hubs": {},
            "ws_registered": False,
            "frontend_ready": None,
            "setup_lock": asyncio.Lock(),
        },
    )

    async with data["setup_lock"]:
        if not data["ws_registered"]:
            websocket_api.async_register_command(hass, _websocket_subscribe_live)
            data["ws_registered"] = True

        if data["frontend_ready"] is None:
            data["frontend_ready"] = await _async_ensure_frontend_resource(hass)
        if data["frontend_ready"]:
            _install_compact_map_entity()

    hubs: dict[str, LiveMapHub] = data["hubs"]
    for coordinator in coordinators:
        serial = coordinator.client.serial_number
        old_hub = hubs.get(serial)
        if isinstance(old_hub, LiveMapHub):
            old_hub.close()
        hub = LiveMapHub(hass, coordinator)
        hubs[serial] = hub

        def remove_hub(*, _serial: str = serial, _hub: LiveMapHub = hub) -> None:
            current = hubs.get(_serial)
            if current is _hub:
                hubs.pop(_serial, None)
            _hub.close()

        entry.async_on_unload(remove_hub)


__all__ = [
    "LIVE_DATA_KEY",
    "LIVE_RESOURCE_PATH",
    "async_setup_live_map_stream",
]
