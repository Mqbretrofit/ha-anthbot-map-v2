"""Data coordinator for Anthbot Genie."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AnthbotBoundDevice,
    AnthbotCloudApiClient,
    AnthbotGenieApiError,
    AnthbotShadowApiClient,
)
from .zones import ridable_areas
from .const import DOMAIN
from .const import (
    ATTR_SERIAL_NUMBER,
    CONF_CHARGE_LIMIT,
    CONF_CHARGER_SWITCH,
    CONF_MAINTENANCE_LEVEL,
    CONF_RESUME_LEVEL,
    DEFAULT_BATTERY_SAVER_CHARGE_LIMIT,
    DEFAULT_BATTERY_SAVER_MAINTENANCE_LEVEL,
    DEFAULT_BATTERY_SAVER_RESUME_LEVEL,
    SERVICE_RESUME_MOW,
)
from .task_events import latest_task_cycle_signal
from .definition_refresh import (
    MapArchiveSelection,
    definition_content,
    map_archive_diagnostics,
    map_definition_cache_key,
    select_map_archive,
    should_refresh_area_definition as _should_refresh_area_definition,
    should_refresh_map_definition,
)
from .mqtt_live import AnthbotLiveShadowListener

_LOGGER = logging.getLogger(__name__)
_LIVE_HISTORY_REFRESH_SECONDS = 5.0
_IDLE_PROPERTY_REFRESH_SECONDS = 60.0
_HISTORY_PATH_REQUEST_SECONDS = 10.0
_HISTORY_PATH_RESPONSE_TIMEOUT_SECONDS = 4.0
_HISTORY_PATH_RESPONSE_POLL_SECONDS = 0.5
_LIVE_STATUS_VALUES = {
    "globalmowing",
    "zonemowing",
    "pointmowing",
    "bordermowing",
    "regionmowing",
    "nestmowing",
    "mowing",
    "gototarget",
    "remotectrl",
    "working",
    "cutting",
    "edgecutting",
    "nyiras",
    "nyir",
    "munka",
    "vagas",
}
_DOCKED_STATUS_VALUES = {"charge", "charging", "chargestart", "idle", "sleep"}
_ROBOT_STATUS_BY_CODE = {
    0: "idle",
    2: "charge",
    3: "sleep",
    6: "globalmowing",
    7: "zonemowing",
    8: "pointmowing",
    10: "backtodock",
    15: "gototarget",
    16: "bordermowing",
    17: "regionmowing",
    18: "nestmowing",
}

_HISTORY_PATH_URL_KEYS = {
    "hisPathUrl",
    "his_path_url",
    "recordPathUrl",
    "record_path_url",
    "historyPathUrl",
    "history_path_url",
    "pathUrl",
    "path_url",
}

_HISTORY_INFO_KEYS = {
    "history_path_info",
    "historyPathInfo",
    "hisPathUrl",
    "recordPathUrl",
    "cleanedCode",
    "CleanedCode",
    "cleanCode",
}


def _is_live_position_state(data: dict[str, Any]) -> bool:
    robot_sta = data.get("robot_sta")
    if isinstance(robot_sta, dict):
        value = robot_sta.get("value")
        if isinstance(value, str):
            return _normalize_status(value) in _LIVE_STATUS_VALUES
    elif isinstance(robot_sta, str):
        return _normalize_status(robot_sta) in _LIVE_STATUS_VALUES
    status = data.get("mower_status")
    return isinstance(status, str) and _normalize_status(status) in _LIVE_STATUS_VALUES


def _normalize_status(value: str) -> str:
    return value.lower().replace("-", "").replace("_", "").replace(" ", "")


_area_definition_content = definition_content
_map_definition_content = definition_content


def is_robot_shadow_fresh(data: dict[str, Any], max_age_seconds: int = 30) -> bool:
    """Return whether the mower shadow contains a recent device timestamp."""
    value = data.get("timestamp")
    timestamp: float | None = None
    if isinstance(value, (int, float)):
        timestamp = float(value)
    elif isinstance(value, str):
        raw = value.strip()
        if raw.isdigit():
            if len(raw) == 14:
                try:
                    timestamp = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(
                        tzinfo=timezone.utc
                    ).timestamp()
                except ValueError:
                    timestamp = None
            else:
                timestamp = float(raw)
    if timestamp is None:
        return False
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    return 0 <= datetime.now(timezone.utc).timestamp() - timestamp <= max_age_seconds


def is_robot_online(data: dict[str, Any], max_age_seconds: int = 30) -> bool:
    """Return whether the mower explicitly reports online or recently replied."""
    online = data.get("online")
    if isinstance(online, bool):
        return online
    if isinstance(online, (int, float)):
        return online == 1
    if isinstance(online, str) and online.strip().lower() in {"1", "true", "on", "online"}:
        return True
    return is_robot_shadow_fresh(data, max_age_seconds=max_age_seconds)


class AnthbotGenieDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch and cache Anthbot shadow state."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        account_client: AnthbotCloudApiClient,
        client: AnthbotShadowApiClient,
        device: AnthbotBoundDevice,
        update_interval: timedelta,
        battery_saver_config: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.account_client = account_client
        self.client = client
        self.device = device
        self._area_definition: dict[str, Any] = {}
        self._ridable_area_definition: dict[str, Any] | list[Any] = {}
        self._ridable_area_definition_error: str | None = None
        self._map_definition: dict[str, Any] | list[Any] | None = None
        self._path_definition: dict[str, Any] | list[Any] | None = None
        self._map_definition_error: str | None = None
        self._path_definition_error: str | None = None
        self._history_path_info: Any = None
        self._history_path_source: str | None = None
        self._mowing_records: dict[str, Any] = {"data": []}
        self._mowing_records_error: str | None = None
        self._task_events: dict[str, Any] = {"data": []}
        self._task_events_error: str | None = None
        self._last_task_event_download_monotonic = 0.0
        self._last_record_download_monotonic = 0.0
        self._error_history: list[dict[str, Any]] = []
        self._last_error_signature: str | None = None
        self._last_area_time: str | None = None
        self._last_area_download_monotonic = 0.0
        self._last_ridable_area_time: str | None = None
        self._last_ridable_area_download_monotonic = 0.0
        self._ridable_area_refresh_lock = asyncio.Lock()
        self._last_map_time: str | None = None
        self._last_map_key: str | None = None
        self._last_map_download_monotonic = 0.0
        self._map_definition_source: str | None = None
        self._last_path_time: str | None = None
        self._last_history_path_request: str | None = None
        self._last_history_path_request_monotonic = 0.0
        self._last_path_download_monotonic = 0.0
        self._last_property_request_monotonic = 0.0
        self._consecutive_cloud_failures = 0
        self._fallback_update_interval = max(update_interval, timedelta(seconds=60))
        self._live_listener: AnthbotLiveShadowListener | None = None
        self._live_listener_task: asyncio.Task[None] | None = None
        self._live_shadow_connected = False
        self._live_shadow_error: str | None = None
        self._pending_live_property: dict[str, Any] = {}
        self._pending_live_service: dict[str, Any] = {}
        self._live_flush_task: asyncio.Task[None] | None = None
        self._last_mowing_task: dict[str, Any] | None = None
        self._battery_saver_config = dict(battery_saver_config or {})
        self._battery_saver_enabled = False
        self._battery_saver_phase = "disabled"
        self._battery_saver_listener_remove = None
        self._battery_saver_task: asyncio.Task[None] | None = None
        self._battery_saver_volume_restore_task: asyncio.Task[None] | None = None
        self._battery_saver_saved_volume: int | None = None
        self._battery_saver_action_lock = asyncio.Lock()
        self._task_store: Store[dict[str, Any]] = Store(
            hass,
            1,
            f"{DOMAIN}.last_mowing_task_{client.serial_number}",
        )
        self._battery_saver_store: Store[dict[str, Any]] = Store(
            hass,
            1,
            f"{DOMAIN}.battery_saver_{client.serial_number}",
        )

    @property
    def reported_state(self) -> dict[str, Any]:
        """Return the latest reported state."""
        return self.data if isinstance(self.data, dict) else {}

    @property
    def live_shadow_connected(self) -> bool:
        """Return whether the app-style MQTT shadow session is active."""
        return self._live_shadow_connected

    def remember_mowing_task(self, task_type: str, data: Any = None) -> None:
        """Remember and persist the task that Pause must later resume."""
        self._last_mowing_task = {"type": task_type, "data": data}
        if self.reported_state:
            state = dict(self.reported_state)
            state["_last_mowing_task"] = dict(self._last_mowing_task)
            self.async_set_updated_data(state)
        snapshot = dict(self._last_mowing_task)
        self.hass.async_create_background_task(
            self._task_store.async_save(snapshot),
            f"anthbot_save_last_task_{self.client.serial_number}",
        )

    async def async_confirm_ridable_area_settings(
        self,
        *,
        previous_time: str | None,
        edge_id: int,
        cutter_height: int,
        ride_distance: int,
        timeout: float = 30.0,
    ) -> None:
        """Wait for the mower to publish and persist a new edge definition."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(2)
            await self.client.async_request_all_properties()
            await self.async_request_refresh()

            current_time = self.reported_state.get("ridable_area_time")
            if not isinstance(current_time, str) or not current_time:
                continue
            if previous_time and current_time == previous_time:
                continue

            for edge in ridable_areas(self.reported_state):
                try:
                    current_id = int(edge.get("id"))
                except (TypeError, ValueError):
                    continue
                if current_id != edge_id:
                    continue
                if (
                    int(edge.get("cutter_height", -1)) == cutter_height
                    and int(edge.get("ride_distance", -1)) == ride_distance
                ):
                    return

            raise AnthbotGenieApiError(
                "The mower published a new edge definition, but it did not contain "
                "the requested settings"
            )

        raise AnthbotGenieApiError(
            "The mower did not confirm the edge-settings update within 30 seconds"
        )

    async def async_clear_last_mowing_task(self) -> None:
        """Forget the resumable task after Stop deletes every mower task."""
        self._last_mowing_task = None
        await self._task_store.async_remove()
        if self.reported_state:
            state = dict(self.reported_state)
            state["_last_mowing_task"] = None
            self.async_set_updated_data(state)

    async def async_load_last_mowing_task(self) -> None:
        """Restore the previous mowing task after a Home Assistant restart."""
        stored = await self._task_store.async_load()
        if not isinstance(stored, dict):
            return
        task_type = stored.get("type")
        if task_type not in {"full", "manual_zone", "auto_zone", "edge", "dock_edge"}:
            return
        self._last_mowing_task = {
            "type": task_type,
            "data": stored.get("data"),
        }

    @property
    def last_mowing_task(self) -> dict[str, Any] | None:
        """Return a copy of the most recently started mowing task."""
        return dict(self._last_mowing_task) if self._last_mowing_task else None

    @property
    def battery_saver_enabled(self) -> bool:
        """Return whether automatic battery-saving behavior is armed."""
        return self._battery_saver_enabled

    @property
    def battery_saver_phase(self) -> str:
        """Return the current state-machine phase for diagnostics."""
        return self._battery_saver_phase

    @property
    def battery_saver_config(self) -> dict[str, Any]:
        """Return normalized per-mower battery saver configuration."""
        try:
            charge_limit = int(
                self._battery_saver_config.get(
                    CONF_CHARGE_LIMIT, DEFAULT_BATTERY_SAVER_CHARGE_LIMIT
                )
            )
        except (TypeError, ValueError):
            charge_limit = DEFAULT_BATTERY_SAVER_CHARGE_LIMIT
        try:
            maintenance_level = int(
                self._battery_saver_config.get(
                    CONF_MAINTENANCE_LEVEL,
                    DEFAULT_BATTERY_SAVER_MAINTENANCE_LEVEL,
                )
            )
        except (TypeError, ValueError):
            maintenance_level = DEFAULT_BATTERY_SAVER_MAINTENANCE_LEVEL
        try:
            resume_level = int(
                self._battery_saver_config.get(
                    CONF_RESUME_LEVEL, DEFAULT_BATTERY_SAVER_RESUME_LEVEL
                )
            )
        except (TypeError, ValueError):
            resume_level = DEFAULT_BATTERY_SAVER_RESUME_LEVEL
        return {
            CONF_CHARGER_SWITCH: self._battery_saver_config.get(CONF_CHARGER_SWITCH),
            CONF_CHARGE_LIMIT: max(20, min(100, charge_limit)),
            CONF_MAINTENANCE_LEVEL: max(10, min(99, maintenance_level)),
            CONF_RESUME_LEVEL: max(10, min(99, resume_level)),
        }

    async def async_load_battery_saver_state(self) -> None:
        """Restore the local battery-saver switch after a restart."""
        stored = await self._battery_saver_store.async_load()
        self._battery_saver_enabled = bool(
            isinstance(stored, dict) and stored.get("enabled") is True
        )
        if isinstance(stored, dict):
            saved_volume = stored.get("saved_volume")
            if isinstance(saved_volume, (int, float)) and 0 <= saved_volume <= 100:
                self._battery_saver_saved_volume = int(saved_volume)
        if self._battery_saver_enabled and isinstance(stored, dict):
            phase = stored.get("phase")
            if phase in {
                "initial_charge",
                "mowing",
                "recovery_charge",
                "manual_charge",
                "waiting_for_task",
                "completed",
            }:
                self._battery_saver_phase = phase
                return
        self._battery_saver_phase = "disabled"

    async def async_set_battery_saver_enabled(self, enabled: bool) -> None:
        """Persist the local battery-saver switch without changing mower settings."""
        self._battery_saver_enabled = enabled
        if enabled:
            status = self._robot_status(self.reported_state)
            self._battery_saver_phase = (
                "mowing" if status in _LIVE_STATUS_VALUES else "initial_charge"
            )
        else:
            self._battery_saver_phase = "disabled"
            await self._async_restore_voice_volume()
        await self._async_save_battery_saver_state()
        if self.reported_state:
            state = dict(self.reported_state)
            state["_battery_saver_enabled"] = enabled
            state["_battery_saver_phase"] = self._battery_saver_phase
            self.async_set_updated_data(state)
        self.async_schedule_battery_saver_evaluation()

    def start_battery_saver_monitor(self) -> None:
        """Start evaluating battery-saving behavior after coordinator updates."""
        if self._battery_saver_listener_remove is not None:
            return
        self._battery_saver_listener_remove = self.async_add_listener(
            self.async_schedule_battery_saver_evaluation
        )
        self.async_schedule_battery_saver_evaluation()

    async def async_stop_battery_saver_monitor(self) -> None:
        """Stop the local battery-saving state machine."""
        if self._battery_saver_listener_remove is not None:
            self._battery_saver_listener_remove()
            self._battery_saver_listener_remove = None
        if self._battery_saver_task is not None:
            self._battery_saver_task.cancel()
            try:
                await self._battery_saver_task
            except asyncio.CancelledError:
                pass
            self._battery_saver_task = None
        if self._battery_saver_volume_restore_task is not None:
            self._battery_saver_volume_restore_task.cancel()
            try:
                await self._battery_saver_volume_restore_task
            except asyncio.CancelledError:
                pass
            self._battery_saver_volume_restore_task = None
        await self._async_restore_voice_volume()

    def async_schedule_battery_saver_evaluation(self) -> None:
        """Schedule one non-reentrant battery-saving evaluation."""
        if self._battery_saver_task is not None and not self._battery_saver_task.done():
            return
        self._battery_saver_task = self.hass.async_create_background_task(
            self._async_evaluate_battery_saver(),
            f"anthbot_battery_saver_{self.client.serial_number}",
        )

    @staticmethod
    def _battery_percentage(data: dict[str, Any]) -> int | None:
        value = data.get("elec")
        seen: set[int] = set()
        while isinstance(value, dict):
            identity = id(value)
            if identity in seen:
                return None
            seen.add(identity)
            value = value.get("value")
        try:
            percentage = int(float(value))
        except (TypeError, ValueError):
            return None
        return percentage if 0 <= percentage <= 100 else None

    @staticmethod
    def _robot_status(data: dict[str, Any]) -> str:
        value = data.get("robot_sta")
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, int):
            return _ROBOT_STATUS_BY_CODE.get(value, str(value))
        return _normalize_status(str(value)) if value is not None else ""

    async def _async_save_battery_saver_state(self) -> None:
        await self._battery_saver_store.async_save(
            {
                "enabled": self._battery_saver_enabled,
                "phase": self._battery_saver_phase,
                "saved_volume": self._battery_saver_saved_volume,
            }
        )

    def _current_voice_volume(self) -> int | None:
        """Return the mower voice volume from the live shadow."""
        value = self.reported_state.get("volume")
        try:
            volume = int(float(value))
        except (TypeError, ValueError):
            return None
        return volume if 0 <= volume <= 100 else None

    async def _async_restore_voice_volume(self) -> None:
        """Restore the volume saved before a smart-plug charging start."""
        volume = self._battery_saver_saved_volume
        if volume is None:
            return
        try:
            await self.client.async_publish_service_command(
                cmd="volume_ctl", data={"volume": volume}
            )
        except Exception as err:  # noqa: BLE001 - retry on the next evaluation.
            _LOGGER.warning(
                "Battery saver could not restore voice volume for %s: %s",
                self.client.serial_number,
                err,
            )
            return
        self._battery_saver_saved_volume = None
        await self._async_save_battery_saver_state()

    async def _async_delayed_voice_volume_restore(self) -> None:
        """Keep charging-start speech muted, then restore the user's volume."""
        try:
            await asyncio.sleep(12)
            await self._async_restore_voice_volume()
        finally:
            self._battery_saver_volume_restore_task = None

    async def _async_mute_charging_announcement(self) -> None:
        """Temporarily mute the mower before energising a docked charger."""
        if self._battery_saver_saved_volume is not None:
            return
        volume = self._current_voice_volume()
        if volume is None or volume <= 0:
            return
        try:
            await self.client.async_publish_service_command(
                cmd="volume_ctl", data={"volume": 0}
            )
        except Exception as err:  # noqa: BLE001 - charging must still be enabled.
            _LOGGER.warning(
                "Battery saver could not mute charging announcement for %s: %s",
                self.client.serial_number,
                err,
            )
            return
        self._battery_saver_saved_volume = volume
        await self._async_save_battery_saver_state()
        await asyncio.sleep(1)

    async def _async_set_charger(self, enabled: bool) -> None:
        if not self._battery_saver_enabled:
            return
        entity_id = self.battery_saver_config.get(CONF_CHARGER_SWITCH)
        if not isinstance(entity_id, str) or not entity_id:
            return
        state = self.hass.states.get(entity_id)
        desired = "on" if enabled else "off"
        if state is not None and state.state == desired:
            return
        if enabled:
            await self._async_mute_charging_announcement()
        try:
            await self.hass.services.async_call(
                "switch",
                "turn_on" if enabled else "turn_off",
                {"entity_id": entity_id},
                blocking=True,
            )
        finally:
            if enabled and self._battery_saver_saved_volume is not None:
                if self._battery_saver_volume_restore_task is not None:
                    self._battery_saver_volume_restore_task.cancel()
                self._battery_saver_volume_restore_task = (
                    self.hass.async_create_background_task(
                        self._async_delayed_voice_volume_restore(),
                        f"anthbot_restore_volume_{self.client.serial_number}",
                    )
                )

    async def _async_maintain_idle_charge(self, battery: int) -> None:
        """Maintain an idle mower between lower and upper charge thresholds."""
        config = self.battery_saver_config
        entity_id = config.get(CONF_CHARGER_SWITCH)
        state = self.hass.states.get(entity_id) if isinstance(entity_id, str) else None
        charger_on = state is not None and state.state == "on"
        if battery >= config[CONF_CHARGE_LIMIT]:
            await self._async_set_charger(False)
        elif charger_on:
            # Once a maintenance charge starts, let it reach the upper limit.
            return
        elif battery <= config[CONF_MAINTENANCE_LEVEL]:
            await self._async_set_charger(True)

    async def _async_refresh_task_events(self) -> None:
        """Refresh cloud events used by the battery-saver state machine."""
        now = time.monotonic()
        if now - self._last_task_event_download_monotonic < 5:
            return
        self._last_task_event_download_monotonic = now
        try:
            self._task_events = await self.account_client.async_get_task_events(
                self.client.serial_number,
                page_size=20,
            )
            self._task_events_error = None
            if self.reported_state:
                state = dict(self.reported_state)
                state["_task_events"] = self._task_events
                state["_task_events_error"] = None
                self.async_set_updated_data(state)
        except AnthbotGenieApiError as err:
            self._task_events_error = str(err)
            _LOGGER.warning(
                "Battery saver could not refresh task events for %s: %s",
                self.client.serial_number,
                err,
            )

    async def _async_evaluate_battery_saver(self) -> None:
        """Apply charge limits and resume only after a cloud code 1021 return."""
        if not self._battery_saver_enabled:
            return
        if (
            self._battery_saver_saved_volume is not None
            and self._battery_saver_volume_restore_task is None
        ):
            # Recover safely if Home Assistant restarted during the short mute.
            await self._async_restore_voice_volume()
        config = self.battery_saver_config
        if not config.get(CONF_CHARGER_SWITCH):
            return
        async with self._battery_saver_action_lock:
            data = self.reported_state
            status = self._robot_status(data)
            battery = self._battery_percentage(data)
            if battery is None:
                return
            is_mowing = status in _LIVE_STATUS_VALUES
            is_docked = status in _DOCKED_STATUS_VALUES

            if is_mowing:
                if self._battery_saver_phase != "mowing":
                    self._battery_saver_phase = "mowing"
                    await self._async_save_battery_saver_state()
                await self._async_set_charger(False)
                return

            if self._battery_saver_phase == "initial_charge":
                if is_docked:
                    await self._async_maintain_idle_charge(battery)
                return

            if self._battery_saver_phase == "mowing" and (
                status == "backtodock" or is_docked
            ):
                # Code 1021 is emitted specifically for an automatic
                # low-battery return. A manual return has 1019/1022 but no
                # 1021, while a finished task has 1014 before docking.
                await self._async_set_charger(True)
                await self._async_refresh_task_events()
                signal = latest_task_cycle_signal(self._task_events)
                if signal == "low_battery_return":
                    self._battery_saver_phase = "recovery_charge"
                    await self._async_save_battery_saver_state()
                elif signal == "completed":
                    self._battery_saver_phase = "completed"
                    await self._async_save_battery_saver_state()
                elif status == "backtodock":
                    self.hass.loop.call_later(
                        5, self.async_schedule_battery_saver_evaluation
                    )
                    return
                else:
                    self._battery_saver_phase = "manual_charge"
                    await self._async_save_battery_saver_state()

            if self._battery_saver_phase == "manual_charge":
                # Re-check once docked in case code 1021 reached the event API
                # slightly after the live status transition.
                await self._async_refresh_task_events()
                if latest_task_cycle_signal(self._task_events) == "low_battery_return":
                    self._battery_saver_phase = "recovery_charge"
                    await self._async_save_battery_saver_state()
                elif is_docked:
                    await self._async_maintain_idle_charge(battery)
                    return

            if self._battery_saver_phase == "completed":
                if self.last_mowing_task is not None:
                    await self.async_clear_last_mowing_task()
                self._battery_saver_phase = "initial_charge"
                await self._async_save_battery_saver_state()
                if is_docked:
                    await self._async_maintain_idle_charge(battery)
                return

            if self._battery_saver_phase != "recovery_charge" or not is_docked:
                return
            if battery < config[CONF_RESUME_LEVEL]:
                await self._async_set_charger(True)
                return
            if self.last_mowing_task is None:
                self._battery_saver_phase = "initial_charge"
                await self._async_save_battery_saver_state()
                await self._async_maintain_idle_charge(battery)
                return
            await self._async_set_charger(False)
            if not self._battery_saver_enabled:
                return
            self._battery_saver_phase = "mowing"
            await self._async_save_battery_saver_state()
            try:
                await self.hass.services.async_call(
                    DOMAIN,
                    SERVICE_RESUME_MOW,
                    {ATTR_SERIAL_NUMBER: self.client.serial_number},
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001 - preserve retry state after command failure.
                self._battery_saver_phase = "recovery_charge"
                await self._async_save_battery_saver_state()
                _LOGGER.error(
                    "Battery saver could not resume the task for %s: %s",
                    self.client.serial_number,
                    err,
                )

    async def async_start_live_shadow(self) -> None:
        """Start the optional AWS IoT push listener."""
        if self._live_listener_task is not None:
            return
        self._live_listener = AnthbotLiveShadowListener(
            session=self.client.session,
            client=self.client,
            on_shadow=self._async_handle_live_shadow,
            on_connection=self._async_handle_live_connection,
        )
        # This listener intentionally runs for the entire lifetime of the
        # config entry.  Registering it as a normal setup task makes Home
        # Assistant wait forever at "Finalizing startup".  A background task
        # is lifecycle-managed without blocking startup completion.
        self._live_listener_task = self.hass.async_create_background_task(
            self._live_listener.async_run(),
            f"anthbot_map_live_shadow_{self.client.serial_number}",
        )

    async def async_stop_live_shadow(self) -> None:
        """Stop the AWS IoT push listener."""
        if self._live_listener is not None:
            await self._live_listener.async_stop()
        if self._live_listener_task is not None:
            self._live_listener_task.cancel()
            try:
                await self._live_listener_task
            except asyncio.CancelledError:
                pass
        if self._live_flush_task is not None:
            self._live_flush_task.cancel()
            try:
                await self._live_flush_task
            except asyncio.CancelledError:
                pass
        self._pending_live_property.clear()
        self._pending_live_service.clear()
        self._live_flush_task = None
        self._live_listener = None
        self._live_listener_task = None
        self._live_shadow_connected = False

    async def _async_handle_live_connection(
        self, connected: bool, error: str | None
    ) -> None:
        was_connected = self._live_shadow_connected
        self._live_shadow_connected = connected
        self._live_shadow_error = None if connected else error
        # Robot shadow state is MQTT-only, exactly like the mobile app.  The
        # coordinator timer remains solely for ancillary REST data (records,
        # maintenance and map files), never as an IoT shadow fallback.
        self.update_interval = timedelta(minutes=5)
        if self.reported_state:
            state = dict(self.reported_state)
            state["_live_shadow_connected"] = connected
            state["_live_shadow_error"] = self._live_shadow_error
            self.async_set_updated_data(state)

    async def _async_handle_live_shadow(
        self, shadow_name: str, reported: dict[str, Any]
    ) -> None:
        if shadow_name == "service":
            self._pending_live_service.update(reported)
        else:
            self._pending_live_property.update(reported)
        if self._live_flush_task is None or self._live_flush_task.done():
            self._live_flush_task = self.hass.async_create_background_task(
                self._async_flush_live_shadow(),
                f"anthbot_map_live_flush_{self.client.serial_number}",
            )

    async def _async_flush_live_shadow(self) -> None:
        """Coalesce a burst of MQTT shadow fragments into one HA update."""
        try:
            while self._pending_live_property or self._pending_live_service:
                await asyncio.sleep(1)
                property_update = self._pending_live_property
                service_update = self._pending_live_service
                self._pending_live_property = {}
                self._pending_live_service = {}

                state = dict(self.reported_state)
                if service_update:
                    service = state.get("_service_reported")
                    merged_service = (
                        dict(service) if isinstance(service, dict) else {}
                    )
                    merged_service.update(service_update)
                    state["_service_reported"] = merged_service
                if property_update:
                    state.update(property_update)
                    state["_robot_online"] = is_robot_online(state)
                    selection = select_map_archive(state)
                    state["_map_archive_selection"] = map_archive_diagnostics(
                        state, selection
                    )
                else:
                    selection = None
                state["_map_definition"] = self._map_definition
                state["_map_definition_error"] = self._map_definition_error
                state["_cloud_connected"] = True
                state["_cloud_last_success"] = datetime.now(timezone.utc).isoformat()
                state["_live_shadow_connected"] = True
                state["_live_shadow_error"] = None
                # Publish live telemetry immediately. A rare map archive
                # download must not delay the mower's position/status update.
                self.async_set_updated_data(state)
                live_ridable_area_time = property_update.get("ridable_area_time")
                if (
                    isinstance(live_ridable_area_time, str)
                    and live_ridable_area_time
                    and live_ridable_area_time != self._last_ridable_area_time
                ):
                    # Reload app-edited edge settings immediately instead of
                    # waiting for the five-minute ancillary refresh interval.
                    await self._async_refresh_ridable_area_definition(
                        live_ridable_area_time,
                        retries=3,
                    )
                    refreshed_state = dict(self.reported_state)
                    refreshed_state["_ridable_area_definition"] = (
                        self._ridable_area_definition
                    )
                    refreshed_state["_ridable_area_definition_error"] = (
                        self._ridable_area_definition_error
                    )
                    self.async_set_updated_data(refreshed_state)

                if selection is not None:
                    diagnostics, attempted = await self._async_refresh_map_definition(
                        state,
                        time.monotonic(),
                        allow_periodic=False,
                    )
                    if attempted:
                        refreshed_state = dict(self.reported_state)
                        refreshed_state["_map_definition"] = self._map_definition
                        refreshed_state["_map_definition_error"] = (
                            self._map_definition_error
                        )
                        refreshed_state["_map_archive_selection"] = diagnostics
                        self.async_set_updated_data(refreshed_state)
        finally:
            self._live_flush_task = None
            if self._pending_live_property or self._pending_live_service:
                self._live_flush_task = self.hass.async_create_background_task(
                    self._async_flush_live_shadow(),
                    f"anthbot_map_live_flush_{self.client.serial_number}",
                )

    async def _async_refresh_map_definition(
        self,
        property_state: dict[str, Any],
        now: float,
        *,
        allow_periodic: bool,
    ) -> tuple[dict[str, Any], bool]:
        """Refresh the live app map, using a saved archive only as fallback."""
        selection: MapArchiveSelection = select_map_archive(property_state)
        diagnostics = map_archive_diagnostics(property_state, selection)
        diagnostics.update(
            {
                "preferred_source": "live_map",
                "active_source": self._map_definition_source,
                "live_file": f"map_{self.client.serial_number}.txt",
                "live_map_time": selection.map_time,
            }
        )
        map_key = map_definition_cache_key(
            self.client.serial_number,
            property_state,
            selection,
        )
        should_refresh = should_refresh_map_definition(
            has_definition=bool(self._map_definition),
            has_error=self._map_definition_error is not None,
            selection_key=map_key,
            last_selection_key=self._last_map_key,
            now=now,
            last_download=self._last_map_download_monotonic,
            allow_periodic=allow_periodic,
        )
        if not should_refresh:
            return diagnostics, False

        # Record the key and attempt before network I/O. MQTT property
        # fragments and normal polling can otherwise create a request storm
        # when the cloud temporarily rejects or has not uploaded the file yet.
        self._last_map_key = map_key
        self._last_map_time = selection.map_time
        self._last_map_download_monotonic = now
        try:
            try:
                refreshed_map_definition = (
                    await self.account_client.async_get_device_map_definition(
                        self.client.serial_number
                    )
                )
                definition_source = "live_map"
            except AnthbotGenieApiError as live_map_err:
                # A temporary live-map error must never replace an already
                # decoded live boundary with an older saved map.
                if (
                    self._map_definition
                    and self._map_definition_source == "live_map"
                ):
                    raise
                _LOGGER.debug(
                    "Anthbot live map unavailable for %s (%s); falling back "
                    "to the app-selected multi_maps archive",
                    self.client.serial_number,
                    live_map_err,
                )
                refreshed_map_definition = (
                    await self.account_client.async_get_device_map_archive(
                        self.client.serial_number,
                        selection.filename,
                        expected_md5=selection.md5,
                    )
                )
                definition_source = "multi_maps_fallback"

            changed = _map_definition_content(
                refreshed_map_definition
            ) != _map_definition_content(self._map_definition)
            if changed:
                _LOGGER.info(
                    "Anthbot map definition changed for %s; refreshing raster boundary",
                    self.client.serial_number,
                )
            # Keep the new download metadata even when the decoded geometry is
            # unchanged, so diagnostics prove which MD5 was actually fetched.
            self._map_definition = refreshed_map_definition
            self._map_definition_source = definition_source
            self._map_definition_error = None
            diagnostics["active_source"] = definition_source
            if isinstance(refreshed_map_definition, dict):
                source = refreshed_map_definition.get("_download_source")
                if isinstance(source, dict):
                    diagnostics["download_source"] = {
                        key: value
                        for key, value in source.items()
                        if key
                        in {
                            "filename",
                            "category",
                            "sub_category",
                            "content_md5",
                            "expected_md5",
                            "md5_matches",
                        }
                    }
            _LOGGER.debug(
                "ANTHBOT MAP DEFINITION:\n%s",
                self._map_definition,
            )
        except Exception as err:  # noqa: BLE001 - map probe must not break updates.
            _LOGGER.debug(
                "Anthbot map definition unavailable for %s: %s",
                self.client.serial_number,
                err,
            )
            self._map_definition_error = str(err)
            if self._map_definition is None:
                self._map_definition = {}

        return diagnostics, True

    async def _async_refresh_ridable_area_definition(
        self,
        ridable_area_time: str | None,
        *,
        retries: int = 1,
    ) -> bool:
        """Reload the editable edge definition from the app's cloud file."""
        async with self._ridable_area_refresh_lock:
            if (
                ridable_area_time is not None
                and ridable_area_time == self._last_ridable_area_time
                and self._ridable_area_definition
            ):
                return False

            attempts = max(1, retries)
            previous_content = definition_content(self._ridable_area_definition)
            for attempt in range(attempts):
                self._last_ridable_area_download_monotonic = time.monotonic()
                try:
                    refreshed_definition = (
                        await self.account_client.async_get_device_ridable_area_definition(
                            self.client.serial_number
                        )
                    )
                    if (
                        attempt + 1 < attempts
                        and self._ridable_area_definition
                        and definition_content(refreshed_definition) == previous_content
                    ):
                        # The timestamp can reach MQTT just before the new cloud
                        # file becomes readable. Give its publication a moment.
                        await asyncio.sleep(1)
                        continue
                    self._ridable_area_definition = refreshed_definition
                    self._ridable_area_definition_error = None
                    self._last_ridable_area_time = ridable_area_time
                    return True
                except AnthbotGenieApiError as err:
                    self._ridable_area_definition_error = str(err)
                    _LOGGER.debug(
                        "Anthbot editable edge definition unavailable for %s: %s",
                        self.client.serial_number,
                        err,
                    )
                    if attempt + 1 < attempts:
                        await asyncio.sleep(1)
            return True

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh ancillary REST data while shadow state remains MQTT-only."""
        try:
            current = self.reported_state
            property_state = {
                key: value
                for key, value in current.items()
                if not key.startswith("_")
            }
            service_value = current.get("_service_reported")
            service_state = (
                dict(service_value) if isinstance(service_value, dict) else {}
            )
            now = time.monotonic()

            area_time = property_state.get("area_time")
            if not isinstance(area_time, str):
                area_time = None
            ridable_area_time = property_state.get("ridable_area_time")
            if not isinstance(ridable_area_time, str):
                ridable_area_time = None
            path_time = property_state.get("path_time")
            if not isinstance(path_time, str):
                path_time = None
            now = time.monotonic()
            is_live = _is_live_position_state(property_state)

            should_refresh_area = _should_refresh_area_definition(
                has_definition=bool(self._area_definition),
                area_time=area_time,
                last_area_time=self._last_area_time,
                now=now,
                last_download=self._last_area_download_monotonic,
            )
            if should_refresh_area:
                # Record the attempt as well as successful downloads so a
                # temporary cloud error cannot cause a request on every poll.
                self._last_area_download_monotonic = now
                try:
                    refreshed_area_definition = (
                        await self.account_client.async_get_device_area_definition(
                            self.client.serial_number
                        )
                    )
                    if _area_definition_content(
                        refreshed_area_definition
                    ) != _area_definition_content(self._area_definition):
                        _LOGGER.info(
                            "Anthbot area definition changed for %s; refreshing boundary",
                            self.client.serial_number,
                        )
                        self._area_definition = refreshed_area_definition

                    _LOGGER.debug(
                        "ANTHBOT AREA DEFINITION:\n%s",
                        self._area_definition,
                    )
                    self._last_area_time = area_time
                except AnthbotGenieApiError:
                    if not self._area_definition:
                        self._area_definition = {}

            should_refresh_ridable_area = (
                self._last_ridable_area_download_monotonic == 0
                or (
                    ridable_area_time is not None
                    and ridable_area_time != self._last_ridable_area_time
                )
                or now - self._last_ridable_area_download_monotonic >= 300
            )
            if should_refresh_ridable_area:
                await self._async_refresh_ridable_area_definition(ridable_area_time)

            map_archive_diagnostics, _ = await self._async_refresh_map_definition(
                property_state,
                now,
                allow_periodic=True,
            )

            should_refresh_path = (
                self._path_definition is None
                or (path_time is not None and path_time != self._last_path_time)
                or (
                    is_live
                    and now - self._last_path_download_monotonic
                    >= _LIVE_HISTORY_REFRESH_SECONDS
                )
            )
            if should_refresh_path:
                try:
                    refreshed_property_state = await self._async_request_history_path(
                        path_time,
                        force=is_live,
                    )
                    if refreshed_property_state is not None:
                        property_state = refreshed_property_state
                        refreshed_path_time = property_state.get("path_time")
                        if isinstance(refreshed_path_time, str):
                            path_time = refreshed_path_time
                    self._history_path_info = _find_history_info(property_state, service_state)
                    history_url = _find_history_path_url(property_state, service_state)
                    if history_url:
                        self._path_definition = (
                            await self.account_client.async_get_device_file_url(
                                history_url,
                                label="history_path",
                            )
                        )
                        self._history_path_source = "url"
                    else:
                        self._path_definition = (
                            await self.account_client.async_get_device_path_definition(
                                self.client.serial_number
                            )
                        )
                        self._history_path_source = "presigned"
                    _LOGGER.debug(
                        "ANTHBOT PATH DEFINITION:\n%s",
                        self._path_definition,
                    )
                    self._path_definition_error = None
                    self._last_path_time = path_time
                    self._last_path_download_monotonic = time.monotonic()
                except Exception as err:  # noqa: BLE001 - discovery probe must never break polling.
                    _LOGGER.debug(
                        "Anthbot path definition unavailable for %s: %s",
                        self.client.serial_number,
                        err,
                    )
                    self._path_definition_error = str(err)
                    if self._path_definition is None:
                        self._path_definition = {}
                    self._last_path_time = path_time
                    self._last_path_download_monotonic = time.monotonic()

            merged_state = dict(property_state)
            try:
                self._task_events = await self.account_client.async_get_task_events(
                    self.client.serial_number,
                    page_size=20,
                )
                self._task_events_error = None
                self._last_task_event_download_monotonic = now
            except AnthbotGenieApiError as err:
                self._task_events_error = str(err)
                self._last_task_event_download_monotonic = now
                _LOGGER.warning(
                    "Anthbot task events unavailable for %s: %s",
                    self.client.serial_number,
                    err,
                )
            if now - self._last_record_download_monotonic >= 300:
                try:
                    self._mowing_records = await self.account_client.async_get_mowing_records(
                        self.client.serial_number,
                        device_id=self.device.device_id if self.device else None,
                    )
                    self._mowing_records_error = None
                    self._last_record_download_monotonic = now
                except AnthbotGenieApiError as err:
                    self._mowing_records_error = str(err)
                    self._last_record_download_monotonic = now
                    _LOGGER.warning(
                        "Anthbot mowing records unavailable for %s: %s",
                        self.client.serial_number,
                        err,
                    )
            error_snapshot = {
                key: property_state.get(key)
                for key in ("error", "event", "err_code", "error_code", "event_code")
                if property_state.get(key) not in (None, 0, "", [], {})
            }
            signature = repr(error_snapshot)
            if error_snapshot and signature != self._last_error_signature:
                self._error_history.insert(0, {
                    "time": datetime.now(timezone.utc).isoformat(),
                    **error_snapshot,
                })
                del self._error_history[50:]
                self._last_error_signature = signature
            merged_state["_service_reported"] = service_state
            merged_state["_mowing_records"] = self._mowing_records
            merged_state["_mowing_records_error"] = self._mowing_records_error
            merged_state["_task_events"] = self._task_events
            merged_state["_task_events_error"] = self._task_events_error
            merged_state["_error_history"] = self._error_history
            merged_state["_area_definition"] = self._area_definition
            merged_state["_ridable_area_definition"] = self._ridable_area_definition
            merged_state["_ridable_area_definition_error"] = self._ridable_area_definition_error
            merged_state["_map_definition"] = self._map_definition
            merged_state["_path_definition"] = self._path_definition
            merged_state["_history_path_info"] = self._history_path_info
            merged_state["_history_path_source"] = self._history_path_source
            merged_state["_history_path_live_refresh"] = is_live
            merged_state["_history_path_refresh_interval"] = _LIVE_HISTORY_REFRESH_SECONDS
            merged_state["_history_path_last_download_monotonic"] = self._last_path_download_monotonic
            merged_state["_map_definition_error"] = self._map_definition_error
            merged_state["_map_archive_selection"] = map_archive_diagnostics
            merged_state["_path_definition_error"] = self._path_definition_error
            merged_state["_cloud_connected"] = True
            merged_state["_cloud_last_success"] = datetime.now(timezone.utc).isoformat()
            merged_state["_robot_online"] = is_robot_online(property_state)
            merged_state["_live_shadow_connected"] = self._live_shadow_connected
            merged_state["_live_shadow_error"] = self._live_shadow_error
            merged_state["_battery_saver_enabled"] = self._battery_saver_enabled
            merged_state["_battery_saver_phase"] = self._battery_saver_phase
            self._consecutive_cloud_failures = 0
            return merged_state
        except AnthbotGenieApiError as err:
            self._consecutive_cloud_failures += 1
            if self.reported_state and self._consecutive_cloud_failures <= 3:
                _LOGGER.warning(
                    "Temporary Anthbot cloud failure for %s (%s/3), keeping last state: %s",
                    self.client.serial_number,
                    self._consecutive_cloud_failures,
                    err,
                )
                stale_state = dict(self.reported_state)
                stale_state["_cloud_connected"] = False
                stale_state["_cloud_error"] = str(err)
                return stale_state
            raise UpdateFailed(str(err)) from err

    async def _async_request_history_path(
        self,
        path_time: str | None,
        *,
        force: bool = False,
    ) -> dict[str, Any] | None:
        """Ask the mower to upload its complete current path before download.

        The official Genie app publishes ``req_all_path`` with integer data
        ``1`` when the map view requests a fresh mowing path. The mower then
        uploads ``path_<serial>.txt`` and changes ``path_time`` in the property
        shadow. Wait for that shadow change so the following presigned download
        cannot race the upload.
        """
        request_key = path_time or "latest"
        now = time.monotonic()
        elapsed = now - self._last_history_path_request_monotonic
        if elapsed < _HISTORY_PATH_REQUEST_SECONDS:
            return None
        if not force and self._last_history_path_request == request_key:
            return None

        try:
            await self.client.async_publish_service_command(
                cmd="req_all_path",
                data=1,
            )
        except AnthbotGenieApiError as err:
            _LOGGER.debug(
                "Anthbot full path request failed for %s: %s",
                self.client.serial_number,
                err,
            )
            return None

        self._last_history_path_request = request_key
        self._last_history_path_request_monotonic = time.monotonic()
        _LOGGER.debug(
            "Requested Anthbot full path upload for %s using req_all_path",
            self.client.serial_number,
        )

        deadline = time.monotonic() + _HISTORY_PATH_RESPONSE_TIMEOUT_SECONDS
        latest_state: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            await asyncio.sleep(_HISTORY_PATH_RESPONSE_POLL_SECONDS)
            current = self.reported_state
            latest_state = {
                key: value
                for key, value in current.items()
                if not key.startswith("_")
            }

            refreshed_path_time = latest_state.get("path_time")
            if (
                isinstance(refreshed_path_time, str)
                and refreshed_path_time
                and refreshed_path_time != path_time
            ):
                _LOGGER.debug(
                    "Anthbot full path upload completed for %s: %s -> %s",
                    self.client.serial_number,
                    path_time,
                    refreshed_path_time,
                )
                return latest_state

        _LOGGER.debug(
            "Anthbot full path upload for %s did not change path_time within %.1f s",
            self.client.serial_number,
            _HISTORY_PATH_RESPONSE_TIMEOUT_SECONDS,
        )
        return latest_state


def _find_history_path_url(*values: Any) -> str | None:
    for value in values:
        found = _walk_for_history_url(value)
        if found:
            return found
    return None


def _walk_for_history_url(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                key in _HISTORY_PATH_URL_KEYS
                and isinstance(item, str)
                and item.startswith(("http://", "https://"))
            ):
                return item
            if key in _HISTORY_INFO_KEYS:
                nested = _walk_for_history_url(item)
                if nested:
                    return nested
        for item in value.values():
            nested = _walk_for_history_url(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = _walk_for_history_url(item)
            if nested:
                return nested
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        if any(part in value.lower() for part in ("path", "history", "record")):
            return value
    return None


def _find_history_info(*values: Any) -> Any:
    for value in values:
        found = _walk_for_history_info(value)
        if found is not None:
            return found
    return None


def _walk_for_history_info(value: Any) -> Any:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _HISTORY_INFO_KEYS:
                return item
        for item in value.values():
            found = _walk_for_history_info(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _walk_for_history_info(item)
            if found is not None:
                return found
    return None
