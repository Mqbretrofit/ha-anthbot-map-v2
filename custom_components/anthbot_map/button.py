"""Button platform for Anthbot Genie actions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AnthbotGenieApiError
from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .commands import (
    async_prepare_cloud_connection,
    async_start_mowing,
    async_start_outer_edge_mowing,
)
from .zones import active_manual_zone_ids, auto_zones, manual_zones

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AnthbotButtonDescription(ButtonEntityDescription):
    """Describes an Anthbot action button."""


BUTTONS: tuple[AnthbotButtonDescription, ...] = (
    AnthbotButtonDescription(
        key="connect_cloud",
        translation_key="connect_cloud",
        name="Connect cloud",
    ),
    AnthbotButtonDescription(
        key="start_full_mow",
        translation_key="start_full_mow",
        name="Start full mow",
    ),
    AnthbotButtonDescription(key="start_outer_edge_mow", name="Start outer edge mow"),
    AnthbotButtonDescription(key="start_dock_edge_mow", name="Mow around charging dock"),
    AnthbotButtonDescription(
        key="stop_mow",
        translation_key="stop_mow",
        name="Stop mow",
    ),
    AnthbotButtonDescription(
        key="return_to_dock",
        translation_key="return_to_dock",
        name="Return to dock",
    ),
    AnthbotButtonDescription(key="resume_mow", name="Resume paused task"),
    AnthbotButtonDescription(key="pause_mow", name="Pause mowing task"),
    AnthbotButtonDescription(key="reset_blade_maintenance", name="Reset blade maintenance"),
    AnthbotButtonDescription(key="reset_camera_maintenance", name="Reset camera maintenance"),
    AnthbotButtonDescription(key="reset_dock_contact_maintenance", name="Reset charging contact maintenance"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot buttons from config entry."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    entities: list[ButtonEntity] = [
        AnthbotButtonEntity(coordinator, description)
        for coordinator in coordinators
        for description in BUTTONS
    ]

    for coordinator in coordinators:
        for zone in manual_zones(coordinator.reported_state):
            zone_id = zone.get("id")
            if not isinstance(zone_id, int):
                continue
            entities.append(
                AnthbotZoneButtonEntity(
                    coordinator=coordinator,
                    zone=zone,
                    zone_kind="manual",
                )
            )
        for zone in auto_zones(coordinator.reported_state):
            zone_id = zone.get("id")
            x = zone.get("x")
            y = zone.get("y")
            if not isinstance(zone_id, int) or not isinstance(x, int) or not isinstance(
                y, int
            ):
                continue
            entities.append(
                AnthbotZoneButtonEntity(
                    coordinator=coordinator,
                    zone=zone,
                    zone_kind="auto",
                )
            )

    async_add_entities(entities)


class AnthbotButtonEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], ButtonEntity
):
    """Anthbot action button entity."""

    entity_description: AnthbotButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        description: AnthbotButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the mower serial so multi-mower cards can scope controls."""
        return {"serial_number": self.coordinator.client.serial_number}

    async def async_press(self) -> None:
        """Run the button action."""
        key = self.entity_description.key
        if key == "connect_cloud":
            connected = await async_prepare_cloud_connection(
                self.coordinator, attempts=3, wait_seconds=5
            )
            if not connected:
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection"
                )
        elif key == "start_full_mow":
            if await async_start_mowing(self.coordinator, app_state=1):
                self.coordinator.remember_mowing_task("full")
        elif key == "start_outer_edge_mow":
            if await async_start_outer_edge_mowing(self.coordinator):
                self.coordinator.remember_mowing_task("edge")
        elif key == "start_dock_edge_mow":
            if not await async_prepare_cloud_connection(
                self.coordinator, mowing_start=True
            ):
                _LOGGER.warning(
                    "Anthbot mower %s did not confirm the wake request; "
                    "attempting dock mowing on the live MQTT transport",
                    self.coordinator.client.serial_number,
                )
            await self.coordinator.client.async_publish_service_command(cmd="nest_mow_start", data=1)
            self.coordinator.remember_mowing_task("dock_edge")
        elif key == "stop_mow":
            await async_prepare_cloud_connection(self.coordinator)
            await self.coordinator.client.async_publish_service_command(cmd="stop_all_tasks")
            await self.coordinator.async_clear_last_mowing_task()
        elif key == "return_to_dock":
            await async_prepare_cloud_connection(self.coordinator)
            await self.coordinator.client.async_publish_service_command(cmd="charge_start")
        elif key == "resume_mow":
            task = self.coordinator.last_mowing_task
            if task is None:
                raise AnthbotGenieApiError(
                    "There is no mowing task to resume; start a new task"
                )
            task_type = task["type"]
            data = task.get("data")
            if task_type == "full":
                if not await async_start_mowing(self.coordinator, app_state=1):
                    raise AnthbotGenieApiError(
                        "The mower did not confirm resuming full-area mowing"
                    )
            elif task_type == "edge":
                if not await async_start_outer_edge_mowing(self.coordinator):
                    raise AnthbotGenieApiError(
                        "The mower did not confirm resuming edge mowing"
                    )
            elif task_type == "dock_edge":
                await async_prepare_cloud_connection(
                    self.coordinator, mowing_start=True
                )
                await self.coordinator.client.async_publish_service_command(
                    cmd="nest_mow_start", data=1
                )
            else:
                if not await async_prepare_cloud_connection(
                    self.coordinator, mowing_start=True
                ):
                    raise AnthbotGenieApiError(
                        "The mower did not confirm its cloud connection"
                    )
                if task_type == "manual_zone":
                    await self.coordinator.client.async_publish_service_command(
                        cmd="custom_area_mow_start", data=data
                    )
                elif task_type == "auto_zone":
                    await self.coordinator.client.async_publish_service_command(
                        cmd="region_mow_start", data=data
                    )
                else:
                    raise AnthbotGenieApiError(
                        f"Unsupported previous mowing task: {task_type}"
                    )
        elif key == "pause_mow":
            # Also recover the current zone when mowing was started from the
            # official app rather than from a Home Assistant button.
            if self.coordinator.last_mowing_task is None:
                active_zone_ids = active_manual_zone_ids(
                    self.coordinator.reported_state
                )
                if active_zone_ids:
                    self.coordinator.remember_mowing_task(
                        "manual_zone", {"id": active_zone_ids}
                    )
                else:
                    self.coordinator.remember_mowing_task("full")
            await async_prepare_cloud_connection(self.coordinator)
            await self.coordinator.client.async_publish_service_command(cmd="mow_pause")
        elif key.startswith("reset_"):
            reset_ids = {
                "reset_blade_maintenance": 1,
                "reset_camera_maintenance": 2,
                "reset_dock_contact_maintenance": 0,
            }
            await self.coordinator.client.async_publish_service_command(
                cmd="robot_maintenance_reset", data={"reset_id": reset_ids[key]}
            )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()


class AnthbotZoneButtonEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], ButtonEntity
):
    """Button entity representing one mower zone."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        zone: dict[str, Any],
        zone_kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._zone = zone
        self._zone_kind = zone_kind
        zone_id = zone["id"]
        zone_name = zone.get("name")
        if not isinstance(zone_name, str) or not zone_name.strip():
            zone_name = str(zone_id)
        # Manual zones already have a user-facing name (for example "Back" or
        # "Zóna 1"), so do not prepend another "Zone" label. Keep automatically
        # detected areas distinguishable without mixing the UI language into the
        # user's zone name.
        self._attr_name = zone_name if zone_kind == "manual" else f"Auto: {zone_name}"
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{zone_kind}_zone_{zone_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def available(self) -> bool:
        """Return whether the zone still exists in current state."""
        zone_id = self._zone.get("id")
        zones = (
            manual_zones(self.coordinator.reported_state)
            if self._zone_kind == "manual"
            else auto_zones(self.coordinator.reported_state)
        )
        return any(zone.get("id") == zone_id for zone in zones)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return zone metadata."""
        attrs: dict[str, Any] = {
            "serial_number": self.coordinator.client.serial_number,
            "zone_type": self._zone_kind,
        }
        for key in (
            "id",
            "name",
            "mow_count",
            "mow_mode",
            "mow_order",
            "cutter_height",
            "enable_adaptive_head",
            "mow_head",
            "visual_ignore_obstacle_switch",
            "obstacle_avoid_level",
            "x",
            "y",
            "vertexs",
            "points",
        ):
            value = self._zone.get(key)
            if value is not None:
                attrs[key] = value
        return attrs

    async def async_press(self) -> None:
        """Start mowing the selected zone."""
        if not await async_prepare_cloud_connection(
            self.coordinator, mowing_start=True
        ):
            raise AnthbotGenieApiError(
                "The mower did not confirm its cloud connection; zone mowing was not started"
            )
        if self._zone_kind == "manual":
            task_data = {"id": [self._zone["id"]]}
            await self.coordinator.client.async_publish_service_command(
                cmd="custom_area_mow_start",
                data=task_data,
            )
            self.coordinator.remember_mowing_task("manual_zone", task_data)
        else:
            task_data = {"points": [[self._zone["x"], self._zone["y"]]]}
            await self.coordinator.client.async_publish_service_command(
                cmd="region_mow_start",
                data=task_data,
            )
            self.coordinator.remember_mowing_task("auto_zone", task_data)
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
