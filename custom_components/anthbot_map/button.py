"""Button platform for Anthbot Genie actions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AnthbotGenieApiError
from .const import (
    CONF_DEVELOPER_INSTALLATION_ID,
    CONF_SEND_AUTOMATIC_DIAGNOSTICS,
    DEVELOPER_DIAGNOSTICS_ENDPOINT,
    DOMAIN,
)
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .commands import (
    async_prepare_cloud_connection,
    async_start_mowing,
    async_start_outer_edge_mowing,
)
from .developer_reporting import async_send_diagnostics_report
from .firmware_diagnostics import (
    build_firmware_diagnostics_report,
    report_filename,
    write_firmware_diagnostics_report,
)
from .zones import active_manual_zone_ids, auto_zones, manual_zones

_LOGGER = logging.getLogger(__name__)
_FIRMWARE_DIAGNOSTICS_EVENT = "anthbot_firmware_diagnostics_ready"
_FIRMWARE_DIAGNOSTICS_MEDIA_DIR = "anthbot-firmware-diagnostics"
_AUTO_DIAGNOSTICS_REPEAT_SECONDS = 60 * 60
_AUTO_DIAGNOSTICS_MIN_SECONDS = 60


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
    AnthbotButtonDescription(
        key="reset_dock_contact_maintenance",
        name="Reset charging contact maintenance",
    ),
    AnthbotButtonDescription(
        key="export_firmware_diagnostics",
        name="Export & send firmware diagnostics",
        icon="mdi:file-upload-outline",
    ),
)


def _entry_option_enabled(entry: ConfigEntry, key: str) -> bool:
    """Return the current option, with config-entry data as initial fallback."""
    if key in entry.options:
        return bool(entry.options.get(key))
    return bool(entry.data.get(key, False))


def _unwrap_simple_value(value: Any) -> Any:
    """Unwrap the common ANTHBOT {value: ...} envelope."""
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def _automatic_diagnostics_trigger(
    state: dict[str, Any],
) -> tuple[str, str] | None:
    """Return a stable trigger/signature for supported automatic reports."""
    check = state.get("_no_go_path_check")
    if isinstance(check, dict) and check.get("crossing_detected") is True:
        signature = (
            "no-go:"
            f"{check.get('path_id')}:"
            f"{check.get('boundary_crossings', 0)}:"
            f"{check.get('points_inside', 0)}:"
            f"{check.get('last_crossing')}"
        )
        return "no_go_path_crossing", signature

    error_code = _unwrap_simple_value(state.get("err_code"))
    try:
        normalized_error = int(error_code)
    except (TypeError, ValueError):
        normalized_error = 0
    if normalized_error != 0:
        return "mower_error_code", f"err-code:{normalized_error}"

    for key, trigger in (
        ("_path_definition_error", "path_definition_error"),
        ("_map_definition_error", "map_definition_error"),
        ("_live_shadow_error", "live_shadow_error"),
    ):
        value = state.get(key)
        if value not in (None, "", False):
            return trigger, f"{trigger}:{value!s}"

    return None


def _install_automatic_diagnostics_reporting(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: AnthbotGenieDataUpdateCoordinator,
) -> None:
    """Install an opt-in, deduplicated coordinator listener for diagnostics."""
    last_signature_sent_at: dict[str, float] = {}
    last_any_sent_at = 0.0

    def _handle_update() -> None:
        nonlocal last_any_sent_at
        if not _entry_option_enabled(entry, CONF_SEND_AUTOMATIC_DIAGNOSTICS):
            return

        installation_id = entry.data.get(CONF_DEVELOPER_INSTALLATION_ID)
        if not isinstance(installation_id, str) or not installation_id:
            return

        state = coordinator.reported_state
        if not isinstance(state, dict):
            return
        detected = _automatic_diagnostics_trigger(state)
        if detected is None:
            return
        trigger, signature = detected

        now = time.monotonic()
        if now - last_any_sent_at < _AUTO_DIAGNOSTICS_MIN_SECONDS:
            return
        previous = last_signature_sent_at.get(signature)
        if previous is not None and now - previous < _AUTO_DIAGNOSTICS_REPEAT_SECONDS:
            return

        # Automatic reports omit the plain serial number and alias; the report
        # retains a one-way serial hash for repeated-fault correlation.
        report = build_firmware_diagnostics_report(
            coordinator,
            include_raw_state=False,
            include_identifiers=False,
        )
        last_signature_sent_at[signature] = now
        last_any_sent_at = now
        session = async_get_clientsession(hass)
        hass.async_create_task(
            async_send_diagnostics_report(
                session,
                DEVELOPER_DIAGNOSTICS_ENDPOINT,
                installation_id=installation_id,
                report=report,
                trigger=trigger,
            )
        )

    unsubscribe = coordinator.async_add_listener(_handle_update)
    entry.async_on_unload(unsubscribe)


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
        AnthbotButtonEntity(coordinator, description, entry)
        for coordinator in coordinators
        for description in BUTTONS
    ]

    for coordinator in coordinators:
        _install_automatic_diagnostics_reporting(hass, entry, coordinator)
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
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._config_entry = entry
        self._attr_unique_id = (
            f"{coordinator.client.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )
        self._last_diagnostics_export: dict[str, Any] | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the mower serial and diagnostics-export metadata."""
        attrs: dict[str, Any] = {
            "serial_number": self.coordinator.client.serial_number
        }
        if (
            self.entity_description.key == "export_firmware_diagnostics"
            and isinstance(self._last_diagnostics_export, dict)
        ):
            attrs.update(self._last_diagnostics_export)
        return attrs

    async def _async_export_firmware_diagnostics(self) -> None:
        """Write the local JSON report and explicitly upload a privacy-filtered copy."""
        local_media_dir = self.hass.config.media_dirs.get("local")
        if not isinstance(local_media_dir, str) or not local_media_dir:
            raise AnthbotGenieApiError(
                "Home Assistant local media directory is unavailable; configure media_source first"
            )

        # Keep the existing local export fully useful to the owner: the local
        # copy may contain the mower serial and alias, but still excludes raw
        # credentials/tokens and raw coordinator state.
        report = build_firmware_diagnostics_report(
            self.coordinator,
            include_raw_state=False,
            include_identifiers=True,
        )
        filename = report_filename(report)
        folder = Path(local_media_dir) / _FIRMWARE_DIAGNOSTICS_MEDIA_DIR
        file_path = folder / filename
        await self.hass.async_add_executor_job(
            write_firmware_diagnostics_report,
            file_path,
            report,
        )

        media_source_id = (
            "media-source://media_source/local/"
            f"{_FIRMWARE_DIAGNOSTICS_MEDIA_DIR}/{filename}"
        )
        no_go = report.get("no_go") if isinstance(report, dict) else {}
        check = no_go.get("check") if isinstance(no_go, dict) else {}
        device = report.get("device") if isinstance(report, dict) else {}

        # Pressing this explicitly named Export & Send button is the user's
        # manual send action. Keep server data aligned with automatic reports:
        # omit the plain serial/alias and retain only the one-way serial hash.
        installation_id = self._config_entry.data.get(CONF_DEVELOPER_INSTALLATION_ID)
        upload_status = "skipped_no_installation_id"
        server_uploaded = False
        if isinstance(installation_id, str) and installation_id:
            server_report = build_firmware_diagnostics_report(
                self.coordinator,
                include_raw_state=False,
                include_identifiers=False,
            )
            server_uploaded = await async_send_diagnostics_report(
                async_get_clientsession(self.hass),
                DEVELOPER_DIAGNOSTICS_ENDPOINT,
                installation_id=installation_id,
                report=server_report,
                trigger="manual_export",
            )
            upload_status = "sent" if server_uploaded else "failed"

        event_data = {
            "entity_id": self.entity_id,
            "serial_number": self.coordinator.client.serial_number,
            "model": self.coordinator.device.model,
            "firmware_version": (
                device.get("firmware_version") if isinstance(device, dict) else None
            ),
            "filename": filename,
            "file_path": str(file_path),
            "media_source_id": media_source_id,
            "media_content_type": "application/json",
            "server_uploaded": server_uploaded,
            "upload_status": upload_status,
            "crossing_detected": (
                check.get("crossing_detected") if isinstance(check, dict) else False
            ),
            "boundary_crossings": (
                check.get("boundary_crossings", 0) if isinstance(check, dict) else 0
            ),
            "points_inside": (
                check.get("points_inside", 0) if isinstance(check, dict) else 0
            ),
            "traversals": (
                check.get("traversals", 0) if isinstance(check, dict) else 0
            ),
        }
        self._last_diagnostics_export = {
            "last_report_filename": filename,
            "last_report_media_source": media_source_id,
            "last_report_created_at": report.get("generated_at"),
            "last_report_server_uploaded": server_uploaded,
            "last_report_upload_status": upload_status,
            "last_report_crossing_detected": event_data["crossing_detected"],
            "last_report_boundary_crossings": event_data["boundary_crossings"],
        }
        self.async_write_ha_state()
        self.hass.bus.async_fire(_FIRMWARE_DIAGNOSTICS_EVENT, event_data)
        if server_uploaded:
            _LOGGER.info(
                "Exported and uploaded ANTHBOT firmware diagnostics for %s to %s",
                self.coordinator.client.serial_number,
                file_path,
            )
        else:
            _LOGGER.warning(
                "Exported ANTHBOT firmware diagnostics for %s to %s, server upload status=%s",
                self.coordinator.client.serial_number,
                file_path,
                upload_status,
            )

    async def async_press(self) -> None:
        """Run the button action."""
        key = self.entity_description.key
        if key == "export_firmware_diagnostics":
            # The explicit manual action saves a local JSON and sends the same
            # diagnostics content in privacy-filtered form to the project server.
            # It does not wake or otherwise command the mower.
            await self._async_export_firmware_diagnostics()
            return
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
            await self.coordinator.client.async_publish_service_command(
                cmd="nest_mow_start", data=1
            )
            self.coordinator.remember_mowing_task("dock_edge")
        elif key == "stop_mow":
            await async_prepare_cloud_connection(self.coordinator)
            await self.coordinator.client.async_publish_service_command(
                cmd="stop_all_tasks"
            )
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