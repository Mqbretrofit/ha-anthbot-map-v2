"""Regression coverage for model-aware ANTHBOT voice-pack support."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"
MODELS = COMPONENT / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_capabilities():
    package_name = "anthbot_voice_models_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(MODELS)]
    sys.modules[package_name] = package

    base_spec = importlib.util.spec_from_file_location(
        f"{package_name}.base", MODELS / "base.py"
    )
    assert base_spec is not None and base_spec.loader is not None
    base = importlib.util.module_from_spec(base_spec)
    sys.modules[f"{package_name}.base"] = base
    base_spec.loader.exec_module(base)

    cap_spec = importlib.util.spec_from_file_location(
        f"{package_name}.capabilities", MODELS / "capabilities.py"
    )
    assert cap_spec is not None and cap_spec.loader is not None
    capabilities = importlib.util.module_from_spec(cap_spec)
    sys.modules[f"{package_name}.capabilities"] = capabilities
    cap_spec.loader.exec_module(capabilities)
    return capabilities


class VoicePackSupportTests(unittest.TestCase):
    def test_m9_family_keeps_volume_but_has_no_spoken_voice_packs(self) -> None:
        capabilities = _load_capabilities()
        for model in ("Anthbot M9", "Anthbot M9 Pro"):
            self.assertIs(capabilities.supports_voice_volume(model, {}), True)
            self.assertIs(capabilities.supports_voice_packages(model, {}), False)

        # A misleading voice-package field must never expose spoken packs on M9.
        self.assertIs(
            capabilities.supports_voice_packages(
                "Anthbot M9 Pro",
                {"voice_status": {"name": "English"}, "volume": 50},
            ),
            False,
        )

    def test_genie_supports_both_voice_volume_and_voice_packs(self) -> None:
        capabilities = _load_capabilities()
        for model in ("Anthbot Genie 1000", "Genie 600"):
            self.assertIs(capabilities.supports_voice_volume(model, {}), True)
            self.assertIs(capabilities.supports_voice_packages(model, {}), True)

        self.assertIs(capabilities.supports_voice_volume("Unknown mower", {}), False)
        self.assertIs(
            capabilities.supports_voice_packages("Unknown mower", {}), False
        )
        self.assertIs(
            capabilities.supports_voice_volume("Future mower", {"volume": 50}),
            True,
        )
        self.assertIs(
            capabilities.supports_voice_packages(
                "Future mower",
                {"music_cfg": {"music_language": "English"}},
            ),
            True,
        )

    def test_voice_install_uses_confirmed_app_command_and_metadata(self) -> None:
        voice = _read(COMPONENT / "voice_packs.py")
        self.assertIn("/api/v1/voice/package/language", voice)
        self.assertIn(
            "anthbotmap.com/api/anthbot/voice-packs",
            voice,
        )
        self.assertIn('cmd="voice_set"', voice)
        for field in (
            '"music_package"',
            '"english_name"',
            '"sex"',
            '"music_url"',
            '"music_md5"',
            '"category": "voice_pack"',
            '"version"',
        ):
            self.assertIn(field, voice)

    def test_all_voice_entry_points_use_capability_guard(self) -> None:
        select = _read(COMPONENT / "select.py")
        number = _read(COMPONENT / "number.py")
        sensor = _read(COMPONENT / "sensor.py")
        coordinator = _read(COMPONENT / "coordinator.py")
        init = _read(COMPONENT / "__init__.py")

        self.assertIn("AnthbotVoicePackSelect", select)
        self.assertIn("supports_voice_packages(", select)
        self.assertIn('description.key != "voice_volume_setting"', number)
        self.assertIn("supports_voice_volume(", number)
        self.assertIn('description.key != "voice_volume"', sensor)
        self.assertIn("supports_voice_volume(", sensor)
        self.assertGreaterEqual(coordinator.count("supports_voice_volume("), 2)
        self.assertIn("Voice volume is not supported by", init)

    def test_cloud_alias_entity_ids_are_migrated_to_map_base(self) -> None:
        init = _read(COMPONENT / "__init__.py")
        self.assertIn("def _async_align_cloud_alias_entity_ids(", init)
        self.assertIn('item.unique_id == f"{serial_number}_map"', init)
        self.assertIn("alias_base = slugify(cloud_alias)", init)
        self.assertIn("new_entity_id=desired_entity_id", init)

    def test_cloud_alias_entities_are_aligned_to_established_ha_prefix(self) -> None:
        init = _read(COMPONENT / "__init__.py")
        block = init.split("def _async_align_cloud_alias_entity_ids", 1)[1]
        block = block.split("def _sync_standalone_frontend", 1)[0]
        self.assertIn("discovered_bases", block)
        self.assertIn("canonical_base", block)
        self.assertIn("historical_bases", block)
        self.assertIn("object_id.startswith(f\"{base}_\")", block)
        self.assertIn("new_entity_id=desired_entity_id", block)
        self.assertIn("cloud_alias=coordinator.device.alias", init)

    def test_map_card_matches_optional_entities_by_mower_serial(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn("const activeSerial = String(", card)
            self.assertIn("candidateSerial !== activeSerial", card)
            self.assertIn("state.attributes?.serial_number", card)

    def test_community_voice_variants_have_distinct_labels_and_keys(self) -> None:
        source = _read(COMPONENT / "voice_packs.py")
        self.assertIn('"community_id": "hu_noemi_standard"', source)
        self.assertIn('"variant_id": "noemi_standard"', source)
        self.assertIn('"variant_name": "Noémi (női) · Standard"', source)
        self.assertIn('if source == "community" and variant_name:', source)
        self.assertIn('display_name = f"{display_name} – {variant_name}"', source)
        self.assertIn("f\"{source}:{community_id or variant_id or ''}:{music_package}:\"", source)
        self.assertIn("COMMUNITY_TECHNICAL_LANGUAGE = \"German\"", source)
        self.assertIn("COMMUNITY_TECHNICAL_SEX = \"girl\"", source)
        self.assertIn("COMMUNITY_TECHNICAL_SLOT = \"German_girl\"", source)
        self.assertIn('"voice_gender": "female"', source)
        self.assertIn("def _technical_voice_slot(", source)
        self.assertIn("def voice_pack_verification_key(", source)
        self.assertIn("def reported_voice_verification_key(", source)
        self.assertIn('return f"{slot}|{pack.version.strip().casefold()}"', source)
        self.assertIn("english_name = COMMUNITY_TECHNICAL_LANGUAGE", source)
        self.assertIn("sex = COMMUNITY_TECHNICAL_SEX", source)
        self.assertIn("voice_gender=voice_gender", source)
        self.assertIn("community_id=community_id", source)
        self.assertIn("technical_slot=technical_slot", source)

    def test_verified_hungarian_community_pack_is_built_in_as_fallback(self) -> None:
        source = _read(COMPONENT / "voice_packs.py")
        self.assertIn('"language": "Magyar"', source)
        self.assertIn('"music_package": 3', source)
        self.assertIn('"version": "1.2.4"', source)
        self.assertIn(
            '"music_md5": "74e1955f019aa422d446a0d367232826"',
            source,
        )
        self.assertIn("_verified_community_fallback()", source)
        self.assertIn("if not packs and use_fallback:", source)

    def test_voice_catalog_auto_refreshes_without_ha_restart(self) -> None:
        select = _read(COMPONENT / "select.py")
        voice = _read(COMPONENT / "voice_packs.py")

        self.assertIn(
            "_VOICE_CATALOG_REFRESH_INTERVAL = timedelta(seconds=60)",
            select,
        )
        self.assertIn("async_track_time_interval(", select)
        self.assertIn("_async_refresh_community_catalog", select)
        self.assertIn("use_fallback=False", select)
        self.assertIn(
            "public_packs = previous_public if community is None else community",
            select,
        )
        self.assertIn(
            "merged_community = merge_community_voice_packs(",
            select,
        )
        self.assertIn(
            "self._apply_catalog(official + merged_community)",
            select,
        )
        self.assertIn("self.async_write_ha_state()", select)
        self.assertIn("use_fallback: bool = True", voice)
        self.assertIn(
            "return _verified_community_fallback() if use_fallback else None",
            voice,
        )

    def test_voice_pack_large_attributes_are_not_recorded(self) -> None:
        select = _read(COMPONENT / "select.py")
        self.assertIn("from homeassistant.const import MATCH_ALL", select)
        self.assertIn(
            "_unrecorded_attributes = frozenset({MATCH_ALL})",
            select,
        )
        self.assertIn('"voice_store_locked_voice_ids"', select)
        self.assertIn('"requested_voice_url"', select)

    def test_paid_voices_are_visible_before_purchase_and_locked(self) -> None:
        select = _read(COMPONENT / "select.py")
        voice = _read(COMPONENT / "voice_packs.py")

        self.assertIn("/api/anthbot/store/voice-packs", voice)
        self.assertIn("locked: bool = False", voice)
        self.assertIn("store_pack_id: str | None = None", voice)
        self.assertIn('_first_text(record, "id", "pack_id")', voice)
        self.assertIn('locked = source == "community" and access == "paid" and music_url is None', voice)
        self.assertIn('label = f"🔒 {label}', voice)
        self.assertIn("def merge_community_voice_packs(", voice)
        self.assertIn("replacement = owned_by_id.get(pack.community_id)", voice)
        self.assertIn("and not pack.locked", select)
        self.assertIn('"locked_community_pack_count"', select)
        self.assertIn('"voice_store_locked_voice_ids"', select)
        self.assertIn("pack.community_id", select)
        self.assertIn("if pack.locked:", select)
        self.assertIn("This Community voice pack must be purchased", select)
        self.assertIn("Community voice store before it can be installed", select)

        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn('requestedValue.startsWith("🔒 ")', card)
            self.assertIn('this.t("voicePurchaseRequired")', card)
            self.assertIn("attrs.voice_store_locked_voice_ids", card)
            self.assertIn('"/api/anthbot/store/direct-checkout"', card)
            self.assertIn('directUrl.searchParams.set("voice_id", voiceId)', card)
            self.assertIn("startVoicePurchaseWatch(requestedValue)", card)
            self.assertIn('"homeassistant", "update_entity"', card)
            self.assertIn("}, 2000)", card)
            self.assertIn("10000,", card)
            self.assertIn("window.setTimeout(() => void refresh(), 1200)", card)
            self.assertIn("window.setTimeout(() => void refresh(), 600)", card)
            self.assertIn("for (const delay of [0, 150, 350, 700])", card)
            self.assertIn("refreshUnlockedVoiceUi()", card)
            self.assertIn("this.refreshVoicePackControl()", card)
            self.assertIn("window.addEventListener(\"focus\"", card)
            self.assertIn("window.open(checkoutUrl", card)
            self.assertIn("attrs.locked_community_pack_count", card)
            self.assertIn('this.t("voiceStorePaidAvailable")', card)
            self.assertIn("./i18n.js?v=2490", card)

        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            self.assertIn("voiceStorePaidAvailable:", i18n)
            self.assertIn("voicePurchaseRequired:", i18n)

    def test_paid_voice_store_is_linked_anonymously_and_auto_refreshes(self) -> None:
        select = _read(COMPONENT / "select.py")
        voice = _read(COMPONENT / "voice_packs.py")

        self.assertIn("secrets.token_urlsafe(32)", select)
        self.assertIn('f"{DOMAIN}.voice_store_client"', select)
        self.assertIn("AnthbotVoicePackSelect(coordinator, store_client_token)", select)
        self.assertIn("self._store_client_token = store_client_token", select)
        self.assertIn("async_create_voice_store_pairing", select)
        self.assertIn("async_get_purchased_voice_packs", select)
        self.assertIn("_VOICE_STORE_PAIR_REFRESH_INTERVAL = timedelta(hours=24)", select)
        self.assertIn("async def async_update(self) -> None:", select)
        self.assertIn("await self._async_refresh_community_catalog(None)", select)
        self.assertIn('"voice_store_url": self._voice_store_url', select)
        self.assertIn('"voice_store_entitlement_count"', select)
        self.assertIn('"purchased_community_pack_count"', select)
        self.assertIn('pack.access == "paid"', select)
        self.assertIn(
            "previous_purchased if purchased is None else purchased",
            select,
        )

        self.assertIn("/api/anthbot/store/client/pair", voice)
        self.assertIn("/api/anthbot/store/client/entitlements", voice)
        self.assertIn('json={"client_token": client_token}', voice)
        self.assertIn('access: str = "free"', voice)
        self.assertIn('access = str(record.get("access") or "free")', voice)
        self.assertIn('entitlement service could not be reached', voice)

        # Store identity must be independent of ANTHBOT/cloud account identity.
        self.assertNotIn('CONF_USERNAME', select)
        self.assertNotIn('serial_number": self._store_client_token', select)

    def test_map_card_opens_linked_store_and_tracks_entitlements(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn("attrs.voice_store_url", card)
            self.assertIn("attrs.voice_store_entitlement_count", card)
            self.assertIn('this.t("voiceStoreOpen")', card)
            self.assertIn('window.open(voiceStoreUrl, "_blank", "noopener,noreferrer")', card)
            self.assertIn('this.t("voiceStorePurchasedCount")', card)
            self.assertIn("attrs.voice_store_error", card)
            self.assertIn("./i18n.js?v=2490", card)

        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            self.assertIn('voiceStoreOpen: "Open Community voice store"', i18n)
            self.assertIn('voiceStoreOpen: "Community Hangbolt megnyitása"', i18n)
            self.assertIn("voiceStorePurchasedCount:", i18n)
            self.assertIn("voiceStoreAutoNote:", i18n)

    def test_voice_install_state_tracks_request_and_mower_confirmation(self) -> None:
        select = _read(COMPONENT / "select.py")
        voice = _read(COMPONENT / "voice_packs.py")

        self.assertIn("normalize_reported_voice_name", voice)
        self.assertIn('"en": "English"', voice)
        self.assertIn('"de": "German"', voice)
        self.assertIn('"German_girl"', voice)
        self.assertIn("elif token in language_names:", voice)
        self.assertIn("Store(", select)
        self.assertIn("requested_voice_pack", select)
        self.assertIn("voice_install_status", select)
        self.assertIn('"metadata_confirmed"', select)
        self.assertIn('"slot_confirmed"', select)
        self.assertIn('name = (', voice)
        self.assertIn('_first_text(cfg, "music_language", "english_name", "language")', voice)
        self.assertIn("slot_version = cfg.get(name)", voice)
        self.assertIn('"community_verified"', select)
        self.assertIn("and version_match", select)
        self.assertIn("and install_success", select)
        self.assertIn('reported_install_state.casefold() == "success"', select)
        self.assertIn("reported_install_progress >= 100", select)
        self.assertIn(
            '_VOICE_CONFIRM_STATUSES = {"verified", "community_verified"}',
            select,
        )
        self.assertIn('"verified"', select)
        self.assertIn('"mismatch"', select)
        self.assertIn('"unconfirmed"', select)
        self.assertIn("_VOICE_VERIFY_DELAYS", select)
        self.assertIn("_VOICE_MAX_COMMAND_ATTEMPTS = 2", select)
        self.assertIn("_VOICE_RETRY_CHECK_INDEX = 2", select)
        self.assertIn('self._requested_pack["command_status"] = "retrying"', select)
        self.assertIn('self._requested_pack["command_status"] = "not_confirmed"', select)
        self.assertIn("_async_verify_requested_pack(pack, requested_at)", select)
        self.assertIn("requested_voice_md5", select)
        self.assertIn("voice_command_attempts", select)
        self.assertIn("voice_verification_finished_at", select)
        self.assertIn("installed_voice_state", select)
        self.assertIn("installed_voice_progress", select)
        self.assertIn("_ambiguous_community_verification_keys", select)
        self.assertIn("voice_pack_verification_key(pack)", select)
        self.assertIn("reported_voice_verification_key(", select)
        self.assertIn("reported_community_id.casefold()", select)
        self.assertIn("requested_community_id.casefold()", select)
        self.assertIn("reported_community_pack", select)
        self.assertIn("reported_community_id", select)
        self.assertIn("requested_community_id", select)
        self.assertIn("requested_voice_variant_id", select)
        self.assertIn("requested_voice_gender", select)
        self.assertIn("requested_voice_technical_slot", select)
        self.assertIn("COMMUNITY_TECHNICAL_SLOT", select)
        self.assertIn("requested_voice_verification_key", select)
        self.assertIn("installed_voice_verification_key", select)
        self.assertIn("community_verification_conflict_count", select)
        self.assertIn("async_get_official_voice_packs", select)
        self.assertIn("def _async_refresh_official_catalog", select)
        self.assertIn('if pack.source == "anthbot":', select)
        self.assertIn("Factory pack URLs are signed/temporary", select)
        self.assertIn("retry_pack = pack", select)
        self.assertIn("async_install_voice_pack(self.coordinator, retry_pack)", select)
        self.assertIn("async_cache_official_voice_pack", voice)
        self.assertIn("OFFICIAL_VOICE_CACHE_URL", voice)
        self.assertIn("factory_voice_cache_used", select)
        self.assertIn("factory_voice_cache_error", select)
        self.assertIn('"download_failed"', select)
        self.assertIn("install_target_match", select)
        self.assertIn('verification["status"] == "download_failed"', select)

    def test_map_card_shows_voice_verification_and_tracks_option_changes(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn("createVoicePackControl()", card)
            self.assertIn("getVoicePackSignature()", card)
            self.assertIn("refreshVoicePackControl()", card)
            self.assertIn("onlyVoicePackChanged", card)
            self.assertIn("currentTile.replaceWith(this.createVoicePackControl())", card)
            self.assertIn("attrs.voice_install_status", card)
            self.assertIn("attrs.requested_voice_pack", card)
            self.assertIn("attrs.installed_voice_name", card)
            self.assertIn('"voiceInstallCommunityVerified"', card)
            self.assertIn('"voiceInstallMetadataConfirmed"', card)
            self.assertIn("attrs.installed_voice_state", card)
            self.assertIn("attrs.installed_voice_progress", card)
            self.assertIn('"voiceInstallSlotConfirmed"', card)
            self.assertIn('"voiceInstallDownloadFailed"', card)
            self.assertIn('"voiceCommandDownloadFailed"', card)
            self.assertIn('["download_failed", "mismatch", "unconfirmed", "failed"]', card)
            self.assertIn('"voiceSelectPlaceholder"', card)
            self.assertIn("attrs.voice_command_status", card)
            self.assertIn("voiceCommandRetrying", card)
            self.assertIn("voiceRetryButton", card)
            self.assertIn("submitVoicePack", card)
            self.assertIn("attrs.reported_community_pack", card)
            self.assertIn("attrs.requested_voice_variant_id", card)
            self.assertIn("attrs.requested_voice_verification_key", card)
            self.assertIn("attrs.installed_voice_verification_key", card)
            self.assertIn('status === "community_verified"', card)
            self.assertIn('voiceInstallCommunityVerifiedShort")}: ${headline}', card)
            self.assertIn("Array.isArray(attrs.options) ? attrs.options : []", card)

        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            self.assertIn('voiceInstallVerified: "✅', i18n)
            self.assertIn("voiceInstallCommunityVerified:", i18n)
            self.assertIn("voiceInstallMetadataConfirmed:", i18n)
            self.assertIn("voiceInstallDownloadFailed:", i18n)
            self.assertIn("voiceCommandDownloadFailed:", i18n)
            self.assertIn('voiceRobotReport: "Robot jelentése"', i18n)
            self.assertIn("voiceCommandConfirmed:", i18n)
            self.assertIn("voiceCommandRetrying:", i18n)
            self.assertIn("voiceRetryButton:", i18n)

    def test_voice_pack_selector_has_persistent_accent_insensitive_search(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn('this.voiceSearchQuery = ""', card)
            self.assertIn('search.type = "search"', card)
            self.assertIn('this.t("voiceSearchPlaceholder")', card)
            self.assertIn('normalize("NFD")', card)
            self.assertIn('replace(/[\\u0300-\\u036f]/g, "")', card)
            self.assertIn('options.filter((value) => normalizeSearch(value).includes(query))', card)
            self.assertIn('voiceSearchNoResults', card)
            self.assertIn('searchCount.textContent = `${filtered.length}/${options.length}`', card)

        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            self.assertIn("voiceSearchPlaceholder:", i18n)
            self.assertIn("voiceSearchNoResults:", i18n)

    def test_voice_store_popup_is_translated_in_all_23_languages(self) -> None:
        expected_languages = (
            "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "sk",
            "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr", "th", "vi",
            "ko", "km",
        )
        keys = (
            "voiceStoreOpen",
            "voiceStoreAutoNote",
            "voiceStorePurchasedCount",
            "voiceStorePaidAvailable",
            "voicePurchaseRequired",
            "voiceStoreUnavailable",
            "voiceManage",
            "voicePopupSubtitle",
            "voiceStoreCompactSummary",
        )
        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            block = i18n.split("const voiceStoreTranslations = {", 1)[1].split(
                "for (const [language, values] of Object.entries(voiceStoreTranslations))",
                1,
            )[0]
            for language in expected_languages:
                marker = f'"{language}":' if "-" in language else f"  {language}:"
                self.assertIn(marker, block)
            for key in keys:
                self.assertEqual(
                    block.count(f"{key}:"),
                    23,
                    f"{key} must be translated in all 23 languages",
                )

    def test_voice_popup_detail_strings_are_translated_in_all_23_languages(self) -> None:
        expected_languages = (
            "en", "hu", "de", "fr", "es", "it", "pt", "nl", "pl", "cs", "sk",
            "ro", "da", "sv", "no", "fi", "zh-CN", "zh-TW", "tr", "th", "vi",
            "ko", "km",
        )
        keys = (
            "voicePack",
            "voiceInstallVerified",
            "voiceInstallVerifiedShort",
            "voiceInstallCommunityVerified",
            "voiceInstallCommunityVerifiedShort",
            "voiceInstallMetadataConfirmed",
            "voiceInstallMetadataConfirmedShort",
            "voiceInstallSlotConfirmed",
            "voiceInstallSlotConfirmedShort",
            "voiceInstallPending",
            "voiceInstallPendingShort",
            "voiceInstallDownloadFailed",
            "voiceInstallDownloadFailedShort",
            "voiceInstallMismatch",
            "voiceInstallMismatchShort",
            "voiceInstallUnconfirmed",
            "voiceInstallUnconfirmedShort",
            "voiceInstallFailed",
            "voiceInstallFailedShort",
            "voiceInstallReported",
            "voiceInstallReportedShort",
            "voiceInstallUnknown",
            "voiceInstallUnknownShort",
            "voiceRobotReport",
            "voiceSelectPlaceholder",
            "voiceSearchPlaceholder",
            "voiceSearchNoResults",
            "voiceCommandSending",
            "voiceCommandSent",
            "voiceCommandRetrying",
            "voiceCommandConfirmed",
            "voiceCommandSlotConfirmed",
            "voiceCommandFailed",
            "voiceCommandRetryFailed",
            "voiceCommandDownloadFailed",
            "voiceCommandNotConfirmed",
            "voiceCommandAttempt",
            "voiceRetryButton",
        )
        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            block = i18n.split("const voicePopupDetailTranslations = {", 1)[1].split(
                "for (const [language, values] of Object.entries(voicePopupDetailTranslations))",
                1,
            )[0]
            for language in expected_languages:
                self.assertIn(
                    f'"{language}":',
                    block,
                    f"{language} must have Voice Pack popup translations",
                )
            for key in keys:
                self.assertEqual(
                    block.count(f'"{key}":'),
                    23,
                    f"{key} must be translated in all 23 languages",
                )

            # Spot-check Latin and non-Latin locales so English fallback cannot
            # accidentally satisfy only the structural parity assertion.
            self.assertIn('"voicePack": "Sprachpaket"', block)
            self.assertIn('"voiceSelectPlaceholder": "— Sprachpaket auswählen —"', block)
            self.assertIn('"voicePack": "语音包"', block)
            self.assertIn('"voicePack": "음성 팩"', block)
            self.assertIn('"voicePack": "កញ្ចប់សំឡេង"', block)

    def test_voice_pack_controls_live_in_popup_with_compact_summary_tile(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn("openVoicePackDialog({ refresh = false } = {})", card)
            self.assertIn('overlay.dataset.role = "voice-pack-dialog"', card)
            self.assertIn('this.createVoicePackControl({ popup: true })', card)
            self.assertIn('createVoicePackControl({ popup = false } = {})', card)
            self.assertIn('grid-template-columns:minmax(0,1fr) auto', card)
            self.assertIn('button.textContent = this.t("voiceManage")', card)
            self.assertIn('this.t("voiceStoreCompactSummary")', card)
            self.assertIn('this.t("voicePopupSubtitle")', card)
            self.assertIn(
                "this.openVoicePackDialog({ refresh: true })",
                card,
            )
            self.assertIn("./i18n.js?v=2490", card)

        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            self.assertIn('voiceManage: "Manage"', i18n)
            self.assertIn('voiceManage: "Kezelés"', i18n)
            self.assertIn("voicePopupSubtitle:", i18n)
            self.assertIn("voiceStoreCompactSummary:", i18n)

    def test_voice_popup_selector_stays_open_and_uses_dark_options(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn("this.voiceDialogInteractionActive = false", card)
            self.assertIn("this.voiceDialogRefreshPending = false", card)
            self.assertIn(
                'activeElement.matches?.("select,input,textarea")',
                card,
            )
            self.assertIn(
                "this.voiceDialogRefreshPending = true",
                card,
            )
            self.assertIn(
                "select.addEventListener(\"pointerdown\", "
                "beginVoiceDialogInteraction)",
                card,
            )
            self.assertIn(
                "select.addEventListener(\"focus\", "
                "beginVoiceDialogInteraction)",
                card,
            )
            self.assertIn(
                "select.addEventListener(\"blur\", "
                "endVoiceDialogInteraction)",
                card,
            )
            self.assertIn(
                "this.openVoicePackDialog({ refresh: true })",
                card,
            )
            self.assertIn(
                "background:#000;color:#fff;color-scheme:dark",
                card,
            )
            self.assertIn(
                'option.style.backgroundColor = "#000"',
                card,
            )
            self.assertIn('option.style.color = "#fff"', card)
            self.assertIn(
                'placeholder.style.backgroundColor = "#000"',
                card,
            )
            self.assertIn('placeholder.style.color = "#fff"', card)

        init = _read(COMPONENT / "__init__.py")
        self.assertIn("2.4.9.0", init)

    def test_voice_pack_tile_is_compact_and_cannot_overflow_grid(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn('tile.style.cssText = "min-width:0;overflow:hidden;', card)
            self.assertIn("-webkit-line-clamp:2", card)
            self.assertIn("overflow-wrap:anywhere", card)
            self.assertIn("white-space:nowrap;overflow:hidden;text-overflow:ellipsis", card)
            self.assertIn('select.style.cssText = "display:block;width:100%;max-width:100%;min-width:0;', card)
            self.assertIn('(statusKeys[status] || "voiceInstallUnknown") + "Short"', card)

        for path in (
            ROOT / "www" / "anthbot-map" / "i18n.js",
            COMPONENT / "frontend" / "i18n.js",
        ):
            i18n = _read(path)
            self.assertIn('voiceInstallPendingShort: "⏳ Visszaigazolásra vár"', i18n)
            self.assertIn('voiceInstallVerifiedShort: "✅ Visszaigazolva"', i18n)

    def test_map_card_rerenders_when_optional_entities_appear(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn('this.optionalEntitySignature = ""', card)
            self.assertIn("getOptionalEntitySignature()", card)
            self.assertIn("this.getVoicePackSignature()", card)
            self.assertIn("previousOptionalSignature !== this.optionalEntitySignature", card)

    def test_map_card_hides_voice_controls_without_voice_entities(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn('voicePack: ["voice_pack", "voice pack"]', card)
            self.assertIn('if (this.getNumberEntity("voiceVolume"))', card)
            self.assertIn('if (this.getSelectEntity("voicePack"))', card)
            self.assertIn(
                'this._hass.callService("select", "select_option"', card
            )
            fallback = card.split("hasSettingFallback(kind)", 1)[1].split(
                "async callSettingFallback", 1
            )[0]
            self.assertNotIn("voiceVolume", fallback)


if __name__ == "__main__":
    unittest.main()
