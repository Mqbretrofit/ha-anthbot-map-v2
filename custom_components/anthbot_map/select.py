"""Select platform for Anthbot Genie zone mowing mode diagnostics."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .models.n8_control import is_n8_model
from .zones import async_update_zone_settings, auto_zones, manual_zones

_MODE_TO_RAW: dict[str, int] = {
    "Normal": 0,
    "Efficient": 1,
}
_RAW_TO_MODE = {value: key for key, value in _MODE_TO_RAW.items()}

_N8_WORK_MODE_TO_RAW: dict[str, int] = {
    "Mulch": 0,
    "Collect": 1,
    "Sweep": 2,
}
_N8_RAW_TO_WORK_MODE = {value: key for key, value in _N8_WORK_MODE_TO_RAW.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anthbot zone mowing-mode select entities."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    entities: list[SelectEntity] = []
    for coordinator in coordinators:
        if is_n8_model(getattr(coordinator.device, "model", None)):
            entities.append(AnthbotN8WorkModeSelect(coordinator))
        for zone_kind, zones in (
            ("manual", manual_zones(coordinator.reported_state)),
            ("auto", auto_zones(coordinator.reported_state)),
        ):
            for zone in zones:
                zone_id = zone.get("id")
                if isinstance(zone_id, int):
                    entities.append(
                        AnthbotZoneMowingModeSelect(
                            coordinator, zone_kind, zone_id
                        )
                    )
    async_add_entities(entities)


class AnthbotN8WorkModeSelect(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SelectEntity
):
    """N8 grass handling mode: mulch, collect or sweep."""

    _attr_has_entity_name = True
    _attr_name = "Mowing work mode"
    _attr_icon = "mdi:grass"
    _attr_options = list(_N8_WORK_MODE_TO_RAW)

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_n8_work_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    @property
    def current_option(self) -> str | None:
        """Return the currently reported N8 work mode."""
        param_set = self.coordinator.reported_state.get("param_set")
        if not isinstance(param_set, dict):
            return None
        value = param_set.get("work_mode")
        try:
            raw = int(value)
        except (TypeError, ValueError):
            return None
        return _N8_RAW_TO_WORK_MODE.get(raw)

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        """Expose the exact raw N8 work-mode value."""
        param_set = self.coordinator.reported_state.get("param_set")
        value = param_set.get("work_mode") if isinstance(param_set, dict) else None
        return {
            "serial_number": self.coordinator.client.serial_number,
            "model": self.coordinator.device.model,
            "raw_work_mode": value,
        }

    async def async_select_option(self, option: str) -> None:
        """Set N8 work mode through the app-compatible param_set command."""
        raw_value = _N8_WORK_MODE_TO_RAW.get(option)
        if raw_value is None:
            raise ValueError(f"Unsupported N8 work mode: {option}")
        await self.coordinator.client.async_publish_service_command(
            cmd="param_set",
            data={"work_mode": raw_value},
        )
        await self.coordinator.async_request_refresh()


class AnthbotZoneMowingModeSelect(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SelectEntity
):
    """Zone mowing mode selector persisted through app-compatible area_set."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:format-list-bulleted"
    _attr_options = list(_MODE_TO_RAW)

    def __init__(
        self,
        coordinator: AnthbotGenieDataUpdateCoordinator,
        zone_kind: str,
        zone_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._zone_kind = zone_kind
        self._zone_id = zone_id
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{zone_kind}_zone_"
            f"{zone_id}_mowing_mode_raw_setting"
        )

        zone = self._find_zone()
        zone_name = zone.get("name") if isinstance(zone, dict) else None
        kind_label = "Auto zone" if zone_kind == "auto" else "Zone"
        self._attr_name = f"{kind_label} {zone_name or zone_id} mowing mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )

    def _find_zone(self) -> dict | None:
        zones = (
            manual_zones(self.coordinator.reported_state)
            if self._zone_kind == "manual"
            else auto_zones(self.coordinator.reported_state)
        )
        return next(
            (zone for zone in zones if zone.get("id") == self._zone_id),
            None,
        )

    @property
    def current_option(self) -> str | None:
        """Return the zone's currently reported mowing mode."""
        zone = self._find_zone()
        if not isinstance(zone, dict):
            return None
        value = zone.get("mow_mode")
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                return None
        if isinstance(value, (int, float)):
            return _RAW_TO_MODE.get(int(value))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        """Expose the exact zone and raw value for diagnosis."""
        zone = self._find_zone()
        value = zone.get("mow_mode") if isinstance(zone, dict) else None
        name = zone.get("name") if isinstance(zone, dict) else None
        return {
            "serial_number": self.coordinator.client.serial_number,
            "model": self.coordinator.device.model,
            "zone_kind": self._zone_kind,
            "zone_id": self._zone_id,
            "zone_name": name,
            "setting": "mowing_mode",
            "raw_mow_mode": value,
        }

    async def async_select_option(self, option: str) -> None:
        """Persist mowing mode on this zone through area_set."""
        raw_value = _MODE_TO_RAW.get(option)
        if raw_value is None:
            raise ValueError(f"Unsupported mowing mode: {option}")

        await async_update_zone_settings(
            self.coordinator,
            zone_kind=self._zone_kind,
            zone_id=self._zone_id,
            updates={"mow_mode": raw_value},
        )
