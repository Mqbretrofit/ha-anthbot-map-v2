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
            "reports.mqbretrofithungary.online/api/anthbot/voice-packs",
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
        self.assertIn("Preserve manually renamed or already aligned entity IDs", init)

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
        self.assertIn("if not packs:", source)

    def test_map_card_rerenders_when_optional_entities_appear(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn('this.optionalEntitySignature = ""', card)
            self.assertIn("getOptionalEntitySignature()", card)
            self.assertIn('this.getSelectEntity("voicePack") || ""', card)
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
