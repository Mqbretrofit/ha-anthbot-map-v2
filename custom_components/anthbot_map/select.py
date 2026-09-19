"""Select platform for Anthbot Genie zone mowing mode diagnostics."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import AnthbotGenieApiError
from .const import DOMAIN
from .coordinator import AnthbotGenieDataUpdateCoordinator
from .models.capabilities import supports_voice_packages
from .models.n8_control import is_n8_model
from .voice_packs import (
    COMMUNITY_TECHNICAL_SLOT,
    VoicePack,
    async_cache_official_voice_pack,
    async_get_community_voice_packs,
    async_get_official_voice_packs,
    async_get_voice_packs,
    async_install_voice_pack,
    installed_voice_identity,
    normalize_reported_voice_name,
    reported_voice_verification_key,
    voice_pack_verification_key,
)
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

_LOGGER = logging.getLogger(__name__)

_VOICE_CATALOG_REFRESH_INTERVAL = timedelta(seconds=60)
_VOICE_INSTALL_PENDING_SECONDS = 180
_VOICE_VERIFY_DELAYS = (2, 8, 20, 45)
_VOICE_CONFIRM_STATUSES = {"verified", "community_verified"}
_VOICE_MAX_COMMAND_ATTEMPTS = 2
_VOICE_RETRY_CHECK_INDEX = 2


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
        if supports_voice_packages(
            getattr(coordinator.device, "model", None),
            coordinator.reported_state,
        ):
            entities.append(AnthbotVoicePackSelect(coordinator))
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


class AnthbotVoicePackSelect(
    CoordinatorEntity[AnthbotGenieDataUpdateCoordinator], SelectEntity
):
    """Select and install an official or community voice pack."""

    _attr_has_entity_name = True
    _attr_name = "Voice pack"
    _attr_icon = "mdi:account-voice"

    def __init__(self, coordinator: AnthbotGenieDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_number}_voice_pack"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.client.serial_number)},
            manufacturer="Anthbot",
            model=coordinator.device.model,
            name=coordinator.device.alias,
        )
        self._catalog_by_label: dict[str, VoicePack] = {}
        self._ambiguous_community_verification_keys: set[str] = set()
        self._attr_options = []
        self._catalog_refresh_lock = asyncio.Lock()
        self._requested_pack: dict[str, object] | None = None
        self._request_store: Store[dict[str, object]] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        serial = self.coordinator.client.serial_number
        self._request_store = Store(
            self.hass,
            1,
            f"{DOMAIN}.voice_pack_request.{serial}",
        )
        stored = await self._request_store.async_load()
        if isinstance(stored, dict):
            self._requested_pack = stored

        self.hass.async_create_background_task(
            self._async_reload_catalog(),
            f"anthbot_voice_catalog_{serial}",
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_refresh_community_catalog,
                _VOICE_CATALOG_REFRESH_INTERVAL,
            )
        )

    async def _async_reload_catalog(self) -> None:
        async with self._catalog_refresh_lock:
            try:
                packs = await async_get_voice_packs(self.coordinator)
            except AnthbotGenieApiError as err:
                _LOGGER.warning(
                    "Could not load ANTHBOT voice catalogue for %s: %s",
                    self.coordinator.client.serial_number,
                    err,
                )
                return

            self._apply_catalog(packs)

    async def _async_refresh_official_catalog(self) -> bool:
        """Refresh expiring ANTHBOT factory voice URLs before installation."""
        async with self._catalog_refresh_lock:
            try:
                official = await async_get_official_voice_packs(
                    self.coordinator.account_client
                )
            except AnthbotGenieApiError as err:
                _LOGGER.warning(
                    "Could not refresh ANTHBOT factory voice catalogue for %s: %s",
                    self.coordinator.client.serial_number,
                    err,
                )
                return False

            community = [
                pack
                for pack in self._catalog_by_label.values()
                if pack.source == "community"
            ]
            self._apply_catalog(official + community)
            return True

    async def _async_refresh_community_catalog(self, _now) -> None:
        """Refresh only the dynamic Community portion without restarting HA."""
        async with self._catalog_refresh_lock:
            community = await async_get_community_voice_packs(
                self.coordinator.account_client._session,
                use_fallback=False,
            )
            if community is None:
                return

            official = [
                pack
                for pack in self._catalog_by_label.values()
                if pack.source == "anthbot"
            ]
            changed = self._apply_catalog(official + community)
            if changed:
                _LOGGER.info(
                    "Updated Community voice catalogue for %s: %s option(s)",
                    self.coordinator.client.serial_number,
                    len(community),
                )

    def _apply_catalog(self, packs: list[VoicePack]) -> bool:
        """Replace the catalogue and track Community identity collisions."""
        new_catalog = {pack.label: pack for pack in packs}
        community_keys: dict[str, list[str]] = {}
        for pack in new_catalog.values():
            if pack.source != "community":
                continue
            verification_key = voice_pack_verification_key(pack)
            community_keys.setdefault(verification_key, []).append(pack.label)

        ambiguous = {
            key
            for key, labels in community_keys.items()
            if len(labels) > 1
        }
        if ambiguous and ambiguous != self._ambiguous_community_verification_keys:
            for key in sorted(ambiguous):
                _LOGGER.warning(
                    "Community voice verification key %s is shared by: %s",
                    key,
                    ", ".join(community_keys[key]),
                )

        old_signature = [
            (pack.label, pack.key, pack.music_url, pack.music_md5)
            for pack in self._catalog_by_label.values()
        ]
        new_signature = [
            (pack.label, pack.key, pack.music_url, pack.music_md5)
            for pack in new_catalog.values()
        ]
        changed = (
            old_signature != new_signature
            or ambiguous != self._ambiguous_community_verification_keys
        )
        self._catalog_by_label = new_catalog
        self._ambiguous_community_verification_keys = ambiguous
        self._attr_options = list(new_catalog)
        if changed:
            self.async_write_ha_state()
        return changed

    def _reported_voice(self) -> dict[str, object | None]:
        state = self.coordinator.reported_state
        package_id, raw_name, version = installed_voice_identity(state)
        normalized_name, normalized_sex = normalize_reported_voice_name(raw_name)
        voice_status = state.get("voice_status")
        status = voice_status if isinstance(voice_status, dict) else {}
        progress = status.get("progress")
        try:
            progress_value = int(progress) if progress is not None else None
        except (TypeError, ValueError):
            progress_value = None
        return {
            "music_package": package_id,
            "raw_name": raw_name,
            "name": normalized_name or raw_name,
            "sex": normalized_sex,
            "version": version,
            "install_state": (
                str(status.get("state")).strip()
                if status.get("state") is not None
                else None
            ),
            "install_progress": progress_value,
            "install_time": status.get("time"),
            "install_id": status.get("id"),
        }

    def _reported_official_label(self) -> str | None:
        reported = self._reported_voice()
        package_id = reported["music_package"]
        reported_name = reported["name"]
        reported_sex = reported["sex"]

        for label, pack in self._catalog_by_label.items():
            if pack.source != "anthbot":
                continue
            if isinstance(reported_name, str) and (
                pack.english_name.casefold() == reported_name.casefold()
            ):
                if (
                    isinstance(reported_sex, str)
                    and pack.sex
                    and pack.sex.casefold() != reported_sex.casefold()
                ):
                    continue
                return label

        if package_id is not None:
            candidates = [
                label
                for label, pack in self._catalog_by_label.items()
                if pack.source == "anthbot"
                and str(pack.music_package) == str(package_id)
            ]
            if len(candidates) == 1:
                return candidates[0]
        return None

    def _reported_community_label(
        self,
        reported: dict[str, object | None] | None = None,
    ) -> str | None:
        """Resolve one Community variant from mower-visible slot + version."""
        current = reported or self._reported_voice()
        verification_key = reported_voice_verification_key(
            current.get("name"),
            current.get("sex"),
            current.get("version"),
        )
        if (
            verification_key is None
            or verification_key in self._ambiguous_community_verification_keys
        ):
            return None

        candidates = [
            label
            for label, pack in self._catalog_by_label.items()
            if pack.source == "community"
            and voice_pack_verification_key(pack) == verification_key
        ]
        return candidates[0] if len(candidates) == 1 else None

    def _community_id_for_label(self, label: object) -> str | None:
        """Return the stable registry ID for one resolved Community label."""
        if not isinstance(label, str):
            return None
        pack = self._catalog_by_label.get(label)
        if pack is None or pack.source != "community":
            return None
        return pack.community_id

    def _request_age_seconds(self) -> float | None:
        if not self._requested_pack:
            return None
        requested_at = self._requested_pack.get("requested_at")
        if not isinstance(requested_at, str):
            return None
        try:
            parsed = datetime.fromisoformat(requested_at)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(
            0.0,
            (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds(),
        )

    def _voice_verification(self) -> dict[str, object]:
        reported = self._reported_voice()
        requested = self._requested_pack
        reported_official = self._reported_official_label()
        reported_community = self._reported_community_label(reported)
        reported_community_id = self._community_id_for_label(reported_community)

        if not requested:
            status = "reported" if any(reported.values()) else "unknown"
            return {
                "status": status,
                "exact": False,
                "slot_match": False,
                "reported_official": reported_official,
                "reported_community": reported_community,
                "reported_community_id": reported_community_id,
                "variant_match": False,
            }

        command_status = str(requested.get("command_status") or "")
        if command_status == "failed":
            return {
                "status": "failed",
                "exact": False,
                "slot_match": False,
                "reported_official": reported_official,
                "reported_community": reported_community,
                "variant_match": False,
            }

        requested_package = requested.get("music_package")
        requested_name = str(requested.get("english_name") or "").strip()
        requested_sex = str(requested.get("sex") or "").strip()
        requested_version = str(requested.get("version") or "").strip()
        requested_source = str(requested.get("source") or "")
        requested_label = str(requested.get("label") or "").strip()
        requested_community_id = str(requested.get("community_id") or "").strip()

        reported_package = reported["music_package"]
        reported_name = reported["name"]
        reported_sex = reported["sex"]
        reported_version = reported["version"]
        reported_install_state = reported["install_state"]
        reported_install_progress = reported["install_progress"]

        package_match = (
            reported_package is not None
            and requested_package is not None
            and str(reported_package) == str(requested_package)
        )
        name_match = (
            isinstance(reported_name, str)
            and bool(requested_name)
            and reported_name.casefold() == requested_name.casefold()
        )
        sex_match = (
            not isinstance(reported_sex, str)
            or not requested_sex
            or reported_sex.casefold() == requested_sex.casefold()
        )
        slot_match = package_match or (name_match and sex_match)

        version_reported = isinstance(reported_version, str) and bool(reported_version)
        version_match = (
            version_reported
            and bool(requested_version)
            and reported_version.casefold() == requested_version.casefold()
        )
        install_success = (
            isinstance(reported_install_state, str)
            and reported_install_state.casefold() == "success"
            and isinstance(reported_install_progress, int)
            and reported_install_progress >= 100
        )
        download_failed = (
            isinstance(reported_install_state, str)
            and reported_install_state.casefold()
            in {"download_failed", "download_fail", "download_error", "failed"}
        )
        variant_match = (
            requested_source == "community"
            and (
                (
                    bool(requested_community_id)
                    and bool(reported_community_id)
                    and requested_community_id.casefold()
                    == reported_community_id.casefold()
                )
                or (
                    not requested_community_id
                    and bool(requested_label)
                    and reported_community == requested_label
                )
            )
        )

        if download_failed:
            status = "download_failed"
            exact = False
        elif (
            requested_source == "community"
            and variant_match
            and slot_match
            and version_match
            and install_success
        ):
            # Field testing on Genie 1000 showed that a successful custom
            # install is reported as:
            #   music_cfg.<slot> == requested version
            #   voice_status.state == "success"
            #   voice_status.progress == 100
            # The mower still does not report the downloaded MD5, so this
            # confirms installation metadata/result, not byte-for-byte content.
            status = "community_verified"
            exact = False
        elif requested_source == "community" and slot_match and version_match:
            status = "metadata_confirmed"
            exact = False
        elif requested_source == "community" and slot_match:
            status = "slot_confirmed"
            exact = False
        elif (
            requested_source == "anthbot"
            and slot_match
            and (version_match or not version_reported)
        ):
            # A factory voice is uniquely described by ANTHBOT language/sex slot.
            status = "verified"
            exact = True
        else:
            age = self._request_age_seconds()
            has_report = any(reported.values())
            if command_status == "not_confirmed":
                status = "mismatch" if has_report else "unconfirmed"
            elif age is None or age < _VOICE_INSTALL_PENDING_SECONDS:
                status = "pending"
            elif has_report:
                status = "mismatch"
            else:
                status = "unconfirmed"
            exact = False

        return {
            "status": status,
            "exact": exact,
            "slot_match": slot_match,
            "reported_official": reported_official,
            "reported_community": reported_community,
            "reported_community_id": reported_community_id,
            "variant_match": variant_match,
        }

    @property
    def current_option(self) -> str | None:
        verification = self._voice_verification()

        reported_community = verification.get("reported_community")
        if isinstance(reported_community, str):
            return reported_community

        if (
            verification["status"] == "verified"
            and self._requested_pack
            and isinstance(self._requested_pack.get("label"), str)
        ):
            label = str(self._requested_pack["label"])
            if label in self._catalog_by_label:
                return label

        # Never claim an exact Community variant from a slot-only match.
        if (
            verification["status"] in {"slot_confirmed", "metadata_confirmed"}
            and self._requested_pack
            and self._requested_pack.get("source") == "community"
        ):
            return None

        reported_official = verification.get("reported_official")
        return reported_official if isinstance(reported_official, str) else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        reported = self._reported_voice()
        verification = self._voice_verification()
        requested = self._requested_pack or {}
        command_status = requested.get("command_status")
        if verification["status"] in {"verified", "community_verified"}:
            command_status = "confirmed"
        elif verification["status"] == "download_failed":
            command_status = "download_failed"
        return {
            "serial_number": self.coordinator.client.serial_number,
            "model": self.coordinator.device.model,
            "voice_supported": True,
            "installed_music_package": reported["music_package"],
            "installed_voice_name": reported["raw_name"],
            "installed_voice_display_name": reported["name"],
            "installed_voice_sex": reported["sex"],
            "installed_voice_version": reported["version"],
            "installed_voice_state": reported["install_state"],
            "installed_voice_progress": reported["install_progress"],
            "installed_voice_time": reported["install_time"],
            "installed_voice_id": reported["install_id"],
            "reported_voice_pack": (
                verification.get("reported_community")
                or verification.get("reported_official")
            ),
            "reported_community_pack": verification.get("reported_community"),
            "reported_community_id": verification.get("reported_community_id"),
            "voice_variant_match": verification.get("variant_match", False),
            "installed_voice_verification_key": reported_voice_verification_key(
                reported["name"],
                reported["sex"],
                reported["version"],
            ),
            "requested_voice_pack": requested.get("label"),
            "requested_community_id": requested.get("community_id"),
            "requested_voice_variant_id": requested.get("variant_id"),
            "requested_voice_gender": requested.get("voice_gender"),
            "requested_voice_technical_slot": (
                COMMUNITY_TECHNICAL_SLOT
                if requested.get("source") == "community"
                else None
            ),
            "requested_voice_verification_key": requested.get("verification_key"),
            "requested_voice_source": requested.get("source"),
            "requested_music_package": requested.get("music_package"),
            "requested_voice_version": requested.get("version"),
            "requested_voice_md5": requested.get("music_md5"),
            "requested_voice_url": requested.get("music_url"),
            "factory_voice_cache_used": requested.get("factory_cache_used", False),
            "factory_voice_cache_error": requested.get("factory_cache_error"),
            "requested_at": requested.get("requested_at"),
            "voice_command_status": command_status,
            "voice_command_attempts": requested.get("command_attempts", 0),
            "voice_command_max_attempts": _VOICE_MAX_COMMAND_ATTEMPTS,
            "voice_last_command_at": requested.get("last_command_at"),
            "voice_confirmation_at": requested.get("confirmation_at"),
            "voice_verification_finished_at": requested.get("verification_finished_at"),
            "voice_last_command_error": requested.get("last_command_error"),
            "voice_install_status": verification["status"],
            "voice_install_exact": verification["exact"],
            "voice_report_matches_slot": verification["slot_match"],
            "official_pack_count": sum(
                1 for pack in self._catalog_by_label.values() if pack.source == "anthbot"
            ),
            "community_pack_count": sum(
                1
                for pack in self._catalog_by_label.values()
                if pack.source == "community"
            ),
            "community_verification_conflict_count": len(
                self._ambiguous_community_verification_keys
            ),
        }

    async def _async_save_requested_pack(self) -> None:
        if self._request_store is not None and self._requested_pack is not None:
            await self._request_store.async_save(self._requested_pack)

    async def _async_verify_requested_pack(
        self,
        pack: VoicePack,
        request_id: str,
    ) -> None:
        """Verify a voice install and retry once if the mower did not switch."""
        for check_index, delay in enumerate(_VOICE_VERIFY_DELAYS):
            await asyncio.sleep(delay)
            if (
                not self._requested_pack
                or self._requested_pack.get("request_id") != request_id
            ):
                return

            try:
                await self.coordinator.client.async_request_all_properties()
                await self.coordinator.async_request_refresh()
            except AnthbotGenieApiError as err:
                _LOGGER.debug(
                    "Voice verification refresh failed for %s: %s",
                    self.coordinator.client.serial_number,
                    err,
                )

            verification = self._voice_verification()
            if verification["status"] in _VOICE_CONFIRM_STATUSES:
                self._requested_pack["command_status"] = "confirmed"
                self._requested_pack["confirmation_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                self._requested_pack["verification_finished_at"] = (
                    self._requested_pack["confirmation_at"]
                )
                await self._async_save_requested_pack()
                self.async_write_ha_state()
                return

            self.async_write_ha_state()

            attempts = int(self._requested_pack.get("command_attempts") or 1)
            if (
                (
                    verification["status"] == "download_failed"
                    or check_index == _VOICE_RETRY_CHECK_INDEX
                )
                and attempts < _VOICE_MAX_COMMAND_ATTEMPTS
            ):
                self._requested_pack["command_attempts"] = attempts + 1
                self._requested_pack["command_status"] = "retrying"
                self._requested_pack["last_command_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                await self._async_save_requested_pack()
                self.async_write_ha_state()

                retry_pack = pack
                if pack.source == "anthbot":
                    refreshed = await self._async_refresh_official_catalog()
                    fresh_pack = self._catalog_by_label.get(pack.label)
                    if (
                        refreshed
                        and fresh_pack is not None
                        and fresh_pack.source == "anthbot"
                    ):
                        retry_pack = fresh_pack

                    retry_pack, cache_used, cache_error = (
                        await async_cache_official_voice_pack(
                            self.coordinator.account_client._session,
                            retry_pack,
                        )
                    )
                    self._requested_pack["factory_cache_used"] = cache_used
                    self._requested_pack["factory_cache_error"] = cache_error
                    self._requested_pack["version"] = retry_pack.version
                    self._requested_pack["verification_key"] = (
                        voice_pack_verification_key(retry_pack)
                    )
                    self._requested_pack["music_url"] = retry_pack.music_url
                    self._requested_pack["music_md5"] = retry_pack.music_md5

                try:
                    await async_install_voice_pack(self.coordinator, retry_pack)
                except Exception as err:
                    self._requested_pack["command_status"] = "retry_failed"
                    self._requested_pack["last_command_error"] = str(err)[:240]
                    await self._async_save_requested_pack()
                    self.async_write_ha_state()
                    _LOGGER.warning(
                        "Voice install retry failed for %s: %s",
                        self.coordinator.client.serial_number,
                        err,
                    )
                else:
                    self._requested_pack["command_status"] = "sent"
                    self._requested_pack.pop("last_command_error", None)
                    await self._async_save_requested_pack()
                    self.async_write_ha_state()

        if (
            not self._requested_pack
            or self._requested_pack.get("request_id") != request_id
        ):
            return

        verification = self._voice_verification()
        if verification["status"] not in _VOICE_CONFIRM_STATUSES:
            self._requested_pack["command_status"] = "not_confirmed"
            self._requested_pack["verification_finished_at"] = (
                datetime.now(timezone.utc).isoformat()
            )
            await self._async_save_requested_pack()
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        pack = self._catalog_by_label.get(option)
        if pack is None:
            await self._async_reload_catalog()
            pack = self._catalog_by_label.get(option)
        if pack is None:
            raise ValueError(f"Unknown voice pack: {option}")

        factory_cache_used = False
        factory_cache_error: str | None = None
        if pack.source == "anthbot":
            # Factory pack URLs are signed/temporary. Fetch fresh metadata, then
            # mirror the binary behind the stable Reporting Server HTTPS URL.
            refreshed = await self._async_refresh_official_catalog()
            fresh_pack = self._catalog_by_label.get(option)
            if refreshed and fresh_pack is not None and fresh_pack.source == "anthbot":
                pack = fresh_pack
            elif not refreshed:
                raise AnthbotGenieApiError(
                    "Could not refresh the ANTHBOT factory voice download URL"
                )
            else:
                raise AnthbotGenieApiError(
                    f"Factory voice pack disappeared from ANTHBOT catalogue: {option}"
                )

            pack, factory_cache_used, factory_cache_error = (
                await async_cache_official_voice_pack(
                    self.coordinator.account_client._session,
                    pack,
                )
            )
            if factory_cache_error:
                _LOGGER.warning(
                    "Factory voice cache unavailable for %s (%s): %s; "
                    "falling back to ANTHBOT URL",
                    self.coordinator.client.serial_number,
                    option,
                    factory_cache_error,
                )

        requested_at = datetime.now(timezone.utc).isoformat()
        self._requested_pack = {
            "label": pack.label,
            "source": pack.source,
            "community_id": pack.community_id,
            "variant_id": pack.variant_id,
            "voice_gender": pack.voice_gender,
            "verification_key": voice_pack_verification_key(pack),
            "music_package": pack.music_package,
            "english_name": pack.english_name,
            "sex": pack.sex,
            "version": pack.version,
            "music_url": pack.music_url,
            "music_md5": pack.music_md5,
            "factory_cache_used": factory_cache_used,
            "factory_cache_error": factory_cache_error,
            "requested_at": requested_at,
            "request_id": requested_at,
            "command_status": "sending",
            "command_attempts": 1,
            "last_command_at": requested_at,
            "confirmation_at": None,
            "verification_finished_at": None,
        }
        await self._async_save_requested_pack()
        self.async_write_ha_state()

        try:
            await async_install_voice_pack(self.coordinator, pack)
        except Exception:
            self._requested_pack["command_status"] = "failed"
            await self._async_save_requested_pack()
            self.async_write_ha_state()
            raise

        self._requested_pack["command_status"] = "sent"
        await self._async_save_requested_pack()
        self.async_write_ha_state()

        try:
            await self.coordinator.client.async_request_all_properties()
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
        except AnthbotGenieApiError as err:
            # The voice_set publish already succeeded. A failed immediate read
            # must not be reported to Home Assistant as a failed install command;
            # the background verifier will keep checking the mower.
            _LOGGER.debug(
                "Initial voice verification refresh failed for %s: %s",
                self.coordinator.client.serial_number,
                err,
            )

        self.hass.async_create_background_task(
            self._async_verify_requested_pack(pack, requested_at),
            f"anthbot_voice_verify_{self.coordinator.client.serial_number}",
        )


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
