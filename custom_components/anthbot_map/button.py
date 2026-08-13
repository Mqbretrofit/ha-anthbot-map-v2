"""Button platform for Anthbot Genie actions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
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
from .commands import async_prepare_cloud_connection, async_start_mowing
from .zones import auto_zones, manual_zones


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
            await async_start_mowing(self.coordinator, app_state=1)
        elif key == "start_outer_edge_mow":
            await async_start_mowing(
                self.coordinator,
                app_state=2,
                expected_modes={"bordermowing", "edgemowing", "gototarget"},
            )
        elif key == "start_dock_edge_mow":
            if not await async_prepare_cloud_connection(self.coordinator):
                raise AnthbotGenieApiError(
                    "The mower did not confirm its cloud connection; dock mowing was not started"
                )
            await self.coordinator.client.async_publish_service_command(cmd="nest_mow_start", data=1)
        elif key == "stop_mow":
            await async_prepare_cloud_connection(self.coordinator)
            await self.coordinator.client.async_publish_service_command(
                cmd="stop_all_tasks", data=1
            )
        elif key == "return_to_dock":
            await async_prepare_cloud_connection(self.coordinator)
            await self.coordinator.client.async_publish_service_command(
                cmd="charge_start", data=1
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
        if not await async_prepare_cloud_connection(self.coordinator):
            raise AnthbotGenieApiError(
                "The mower did not confirm its cloud connection; zone mowing was not started"
            )
        if self._zone_kind == "manual":
            await self.coordinator.client.async_publish_service_command(
                cmd="custom_area_mow_start",
                data={"id": [self._zone["id"]]},
            )
        else:
            await self.coordinator.client.async_publish_service_command(
                cmd="region_mow_start",
                data={"points": [[self._zone["x"], self._zone["y"]]]},
            )
        await self.coordinator.client.async_request_all_properties()
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()
