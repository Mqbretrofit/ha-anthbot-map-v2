"""Device tracker platform for Anthbot Genie (GPS position)."""

from __future__ import annotations

from typing import Any

try:
    # New Home Assistant versions export TrackerEntity from the package.
    from homeassistant.components.device_tracker import TrackerEntity
except ImportError:
    # Compatibility with currently supported Home Assistant releases.
    from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AREA_CODE,
    CONF_DEVELOPER_INSTALLATION_ID,
    CONF_SHARE_ANONYMOUS_USAGE,
    DEVELOPER_TELEMETRY_ENDPOINT,
    DOMAIN,
)
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .developer_agent import async_register_developer_agent
from .developer_agent_optin import async_register_developer_agent_optin
from .developer_optin import async_register_developer_optin
from .developer_reporting import async_send_anonymous_usage_report
from .robot_error_reporting import async_register_robot_error_reporting


def _safe_get(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _entry_option(entry: ConfigEntry, key: str, default: bool = False) -> bool:
    """Read a boolean option while preserving legacy config-entry data."""
    if key in entry.options:
        return bool(entry.options.get(key))
    return bool(entry.data.get(key, default))


def _entry_value(entry: ConfigEntry, key: str) -> Any:
    """Read a value from options first and fall back to config-entry data."""
    if key in entry.options:
        return entry.options.get(key)
    return entry.data.get(key)


async def _async_schedule_usage_heartbeat(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinators: list[AnthbotGenieDataUpdateCoordinator],
) -> None:
    """Refresh anonymous installation metadata after each integration load.

    The reporting server stores the integration version from the latest usage
    event. Previously that event was sent only when the user first opted in, so
    HACS updates could leave the dashboard showing an old beta/stable version.
    When anonymous usage reporting is enabled, send one non-blocking heartbeat
    on each config-entry setup/reload so the server sees the version that is
    actually running. No heartbeat is sent when anonymous reporting is off.
    """
    if not _entry_option(entry, CONF_SHARE_ANONYMOUS_USAGE, False):
        return

    installation_id = _entry_value(entry, CONF_DEVELOPER_INSTALLATION_ID)
    if not isinstance(installation_id, str) or not installation_id:
        return

    devices = [
        coordinator.device
        for coordinator in coordinators
        if getattr(coordinator, "device", None) is not None
    ]
    if not devices:
        return

    session = async_get_clientsession(hass)
    hass.async_create_task(
        async_send_anonymous_usage_report(
            session,
            DEVELOPER_TELEMETRY_ENDPOINT,
            installation_id=installation_id,
            area_code=_entry_value(entry, CONF_AREA_CODE),
            devices=devices,
            home_assistant_version=HA_VERSION,
            event="heartbeat",
        ),
        f"anthbot_usage_heartbeat_{entry.entry_id}",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the mower location tracker from a config entry."""
    # Developer-reporting consent and the read-only developer agent are
    # intentionally registered from this small independent platform so mower
    # control, map rendering and Battery Saver remain untouched.
    await async_register_developer_optin(hass)
    await async_register_developer_agent_optin(hass)
    await async_register_developer_agent(hass, entry)

    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    await _async_schedule_usage_heartbeat(hass, entry, coordinators)
    await async_register_robot_error_reporting(hass, entry, coordinators)

    async_add_entities(
        AnthbotLocationTracker(coordinator) for coordinator in coordinators
    )


class AnthbotLocationTracker(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], TrackerEntity
):
    """Tracks the mower's GPS position as reported in the anti_loss_pose shadow field."""

    _attr_has_entity_name = True
    _attr_name = "Location"
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_location"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        value = _safe_get(
            self.coordinator.reported_state, "anti_loss_pose", "posegps", "lat"
        )
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @property
    def longitude(self) -> float | None:
        value = _safe_get(
            self.coordinator.reported_state, "anti_loss_pose", "posegps", "lon"
        )
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw local pose (cm / hundredths of degree) as attributes."""
        state = self.coordinator.reported_state
        pose = state.get("pose") if isinstance(state.get("pose"), dict) else {}
        return {
            "serial_number": self.coordinator.client.serial_number,
            "pose_x": pose.get("x"),
            "pose_y": pose.get("y"),
            "pose_yaw": pose.get("yaw"),
            "pose_type": _safe_get(state, "anti_loss_pose", "pose_type"),
        }
