"""Data coordinator for Anthbot Genie."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AnthbotBoundDevice,
    AnthbotCloudApiClient,
    AnthbotGenieApiError,
    AnthbotShadowApiClient,
)
from .const import DOMAIN

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


def _select_map_file(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return the active multi_maps archive name and md5 from the shadow.

    The map file name comes from the device's ``multi_maps.map_list`` entries
    (for example ``map_<serial>_0``). The entry whose ``map_id`` matches the
    latest ``map_tar_time``/``map_time`` wins; otherwise the first entry is
    used. Returns ``(map_file_name, md5)`` or ``(None, None)`` when the shadow
    exposes no multi_maps list.
    """
    multi_maps = data.get("multi_maps")
    if isinstance(multi_maps, dict):
        map_list = multi_maps.get("map_list")
    else:
        map_list = None
    if not isinstance(map_list, list):
        return None, None
    active_ids = [
        str(value)
        for key in ("map_tar_time", "map_time")
        if isinstance((value := data.get(key)), (str, int))
    ]
    entries = [
        item
        for item in map_list
        if isinstance(item, dict)
        and isinstance(item.get("map_file_name"), str)
        and item["map_file_name"]
    ]
    if not entries:
        return None, None
    entry = next(
        (item for item in entries if str(item.get("map_id")) in active_ids),
        entries[0],
    )
    md5 = entry.get("md5")
    return entry["map_file_name"], str(md5) if isinstance(md5, str) and md5 else None


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
        self._map_definition: dict[str, Any] | list[Any] | None = None
        self._path_definition: dict[str, Any] | list[Any] | None = None
        self._map_definition_error: str | None = None
        self._path_definition_error: str | None = None
        self._history_path_info: Any = None
        self._history_path_source: str | None = None
        self._last_area_time: str | None = None
        self._last_map_time: str | None = None
        self._last_map_key: str | None = None
        self._last_path_time: str | None = None
        self._last_history_path_request: str | None = None
        self._last_history_path_request_monotonic = 0.0
        self._last_path_download_monotonic = 0.0
        self._last_property_request_monotonic = 0.0
        self._consecutive_cloud_failures = 0

    @property
    def reported_state(self) -> dict[str, Any]:
        """Return the latest reported state."""
        return self.data if isinstance(self.data, dict) else {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest state from the cloud endpoint."""
        try:
            property_state = await self.client.async_get_shadow_reported_state()
            now = time.monotonic()
            is_live_hint = _is_live_position_state(
                property_state
            ) or _is_live_position_state(self.reported_state)
            property_refresh_seconds = (
                _LIVE_HISTORY_REFRESH_SECONDS
                if is_live_hint
                else _IDLE_PROPERTY_REFRESH_SECONDS
            )
            if (
                self._last_property_request_monotonic == 0.0
                or now - self._last_property_request_monotonic
                >= property_refresh_seconds
            ):
                try:
                    await self.client.async_request_all_properties()
                    self._last_property_request_monotonic = time.monotonic()
                    await asyncio.sleep(0.5)
                    property_state = await self.client.async_get_shadow_reported_state()
                except AnthbotGenieApiError as err:
                    _LOGGER.debug(
                        "Anthbot property refresh request failed for %s: %s",
                        self.client.serial_number,
                        err,
                    )
            try:
                service_state = await self.client.async_get_service_reported_state()
            except AnthbotGenieApiError:
                service_state = {}

            area_time = property_state.get("area_time")
            if not isinstance(area_time, str):
                area_time = None
            map_time = property_state.get("map_time")
            if not isinstance(map_time, str):
                map_time = None
            map_tar_time = property_state.get("map_tar_time")
            if not isinstance(map_tar_time, str):
                map_tar_time = None
            path_time = property_state.get("path_time")
            if not isinstance(path_time, str):
                path_time = None
            now = time.monotonic()
            is_live = _is_live_position_state(property_state)

            should_refresh_area = not self._area_definition or (
                area_time is not None and area_time != self._last_area_time
            )
            if should_refresh_area:
                try:
                    self._area_definition = (
                        await self.account_client.async_get_device_area_definition(
                            self.client.serial_number
                        )
                    )
                    
                    _LOGGER.debug(
                        "ANTHBOT AREA DEFINITION:\n%s",
                        self._area_definition,
                    )
                    self._last_area_time = area_time
                except AnthbotGenieApiError:
                    if not self._area_definition:
                        self._area_definition = {}

            map_file_name, map_md5 = _select_map_file(property_state)
            map_key = "|".join(
                part
                for part in (map_tar_time, map_time, map_file_name, map_md5)
                if part is not None
            ) or f"map_{self.client.serial_number}_0"

            should_refresh_map = (
                self._map_definition is None
                or self._map_definition_error is not None
                or map_key != self._last_map_key
            )
            if should_refresh_map:
                try:
                    try:
                        self._map_definition = (
                            await self.account_client.async_get_device_map_archive(
                                self.client.serial_number,
                                map_file_name,
                            )
                        )
                    except AnthbotGenieApiError as archive_err:
                        _LOGGER.debug(
                            "Anthbot multi_maps map archive unavailable for %s (%s); "
                            "falling back to legacy map definition",
                            self.client.serial_number,
                            archive_err,
                        )
                        self._map_definition = (
                            await self.account_client.async_get_device_map_definition(
                                self.client.serial_number
                            )
                        )
                    _LOGGER.debug(
                        "ANTHBOT MAP DEFINITION:\n%s",
                        self._map_definition,
                    )
                    self._map_definition_error = None
                    self._last_map_time = map_time
                    self._last_map_key = map_key
                except Exception as err:  # noqa: BLE001 - discovery probe must never break polling.
                    _LOGGER.debug(
                        "Anthbot map definition unavailable for %s: %s",
                        self.client.serial_number,
                        err,
                    )
                    self._map_definition_error = str(err)
                    if self._map_definition is None:
                        self._map_definition = {}
                    self._last_map_time = map_time
                    self._last_map_key = map_key

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
                    try:
                        service_state = await self.client.async_get_service_reported_state()
                    except AnthbotGenieApiError:
                        service_state = service_state or {}
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
            merged_state["_service_reported"] = service_state
            merged_state["_area_definition"] = self._area_definition
            merged_state["_map_definition"] = self._map_definition
            merged_state["_path_definition"] = self._path_definition
            merged_state["_history_path_info"] = self._history_path_info
            merged_state["_history_path_source"] = self._history_path_source
            merged_state["_history_path_live_refresh"] = is_live
            merged_state["_history_path_refresh_interval"] = _LIVE_HISTORY_REFRESH_SECONDS
            merged_state["_history_path_last_download_monotonic"] = self._last_path_download_monotonic
            merged_state["_map_definition_error"] = self._map_definition_error
            merged_state["_path_definition_error"] = self._path_definition_error
            merged_state["_cloud_connected"] = True
            merged_state["_cloud_last_success"] = datetime.now(timezone.utc).isoformat()
            merged_state["_robot_online"] = is_robot_online(property_state)
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
            try:
                latest_state = (
                    await self.client.async_get_shadow_reported_state()
                )
            except AnthbotGenieApiError as err:
                _LOGGER.debug(
                    "Anthbot path_time check failed for %s: %s",
                    self.client.serial_number,
                    err,
                )
                continue

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
