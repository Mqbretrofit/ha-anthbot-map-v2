"""Device tracker platform for Anthbot Genie (GPS position)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator


def _safe_get(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the mower location tracker from a config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
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
