"""Update platform for official ANTHBOT mower firmware."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AnthbotGenieApiError
from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .firmware_update import (
    FirmwareInfo,
    async_start_vendor_firmware_update,
    automatic_update_value,
    installed_firmware_version,
    normalize_firmware_info,
    ota_in_progress,
    ota_status,
)

_LOGGER = logging.getLogger(__name__)
_FIRMWARE_CHECK_INTERVAL_SECONDS = 6 * 60 * 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one firmware update entity per discovered mower."""
    coordinators: list[AnthbotGenieDataUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]
    async_add_entities(AnthbotFirmwareUpdateEntity(item) for item in coordinators)


class AnthbotFirmwareUpdateEntity(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], UpdateEntity
):
    """Official ANTHBOT firmware update entity."""

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_translation_key = "firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_firmware"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )
        self._firmware: FirmwareInfo | None = None
        self._last_firmware_check = 0.0
        self._firmware_check_in_progress = False

    async def async_added_to_hass(self) -> None:
        """Load firmware metadata without delaying integration startup."""
        await super().async_added_to_hass()
        self.hass.async_create_background_task(
            self._async_refresh_firmware_metadata(),
            f"anthbot_firmware_check_{self.coordinator.client.serial_number}",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write live OTA progress and periodically refresh the vendor catalogue."""
        super()._handle_coordinator_update()
        if (
            not self._firmware_check_in_progress
            and time.monotonic() - self._last_firmware_check
            >= _FIRMWARE_CHECK_INTERVAL_SECONDS
        ):
            self.hass.async_create_background_task(
                self._async_refresh_firmware_metadata(),
                f"anthbot_firmware_check_{self.coordinator.client.serial_number}",
            )

    async def _async_refresh_firmware_metadata(self) -> None:
        if self._firmware_check_in_progress:
            return
        self._firmware_check_in_progress = True
        try:
            raw = await self.coordinator.account_client.async_get_latest_firmware(
                self.coordinator.client.serial_number
            )
            self._firmware = normalize_firmware_info(raw)
            self._last_firmware_check = time.monotonic()
        except AnthbotGenieApiError as err:
            _LOGGER.debug(
                "Could not refresh firmware metadata for %s: %s",
                self.coordinator.client.serial_number,
                err,
            )
        finally:
            self._firmware_check_in_progress = False
            if self.hass is not None:
                self.async_write_ha_state()

    @property
    def installed_version(self) -> str | None:
        return installed_firmware_version(self.coordinator.reported_state)

    @property
    def latest_version(self) -> str | None:
        return self._firmware.version if self._firmware else None

    @property
    def title(self) -> str:
        return f"{self.coordinator.device.model} firmware"

    @property
    def auto_update(self) -> bool:
        return automatic_update_value(self.coordinator.reported_state) is True

    @property
    def in_progress(self) -> bool:
        return ota_in_progress(self.coordinator.reported_state)

    @property
    def update_percentage(self) -> int | float | None:
        _state, progress = ota_status(self.coordinator.reported_state)
        return progress if self.in_progress else None

    @property
    def release_summary(self) -> str | None:
        if self._firmware is None or not self._firmware.description:
            return None
        return self._firmware.description[:255]

    async def async_release_notes(self) -> str | None:
        if self._firmware is None:
            await self._async_refresh_firmware_metadata()
        return self._firmware.description if self._firmware else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ota_state, ota_progress = ota_status(self.coordinator.reported_state)
        attrs: dict[str, Any] = {
            "serial_number": self.coordinator.client.serial_number,
            "model": self.coordinator.device.model,
            "automatic_update": automatic_update_value(
                self.coordinator.reported_state
            ),
            "ota_state": ota_state or None,
            "ota_progress": ota_progress,
        }
        if self._firmware is not None:
            attrs.update(
                {
                    "firmware_id": self._firmware.firmware_id,
                    "upgrade_mode": self._firmware.upgrade_mode,
                }
            )
        return attrs

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Install only the firmware currently offered by ANTHBOT."""
        if backup:
            raise HomeAssistantError(
                "Firmware backup is not supported by the ANTHBOT mower protocol"
            )

        await self._async_refresh_firmware_metadata()
        firmware = self._firmware
        if firmware is None:
            raise HomeAssistantError("ANTHBOT did not offer a firmware update")

        if version is not None and version != firmware.version:
            raise HomeAssistantError(
                "Only the firmware version currently offered by ANTHBOT can be installed"
            )

        current = self.installed_version
        if current is not None and current == firmware.version:
            raise HomeAssistantError("The mower already reports this firmware version")

        try:
            await async_start_vendor_firmware_update(self.coordinator, firmware)
        except AnthbotGenieApiError as err:
            raise HomeAssistantError(str(err)) from err

        await self.coordinator.client.async_request_all_properties()
        await self.coordinator.async_request_refresh()
