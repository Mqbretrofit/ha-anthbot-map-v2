"""Regression coverage for model-aware ANTHBOT voice-pack support."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


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


def test_m9_family_keeps_volume_but_has_no_spoken_voice_packs() -> None:
    capabilities = _load_capabilities()
    for model in ("Anthbot M9", "Anthbot M9 Pro"):
        assert capabilities.supports_voice_volume(model, {}) is True
        assert capabilities.supports_voice_packages(model, {}) is False

    # Even misleading voice-package fields must not expose spoken packs on M9.
    assert capabilities.supports_voice_packages(
        "Anthbot M9 Pro", {"voice_status": {"name": "English"}, "volume": 50}
    ) is False


def test_genie_supports_both_voice_volume_and_voice_packs() -> None:
    capabilities = _load_capabilities()
    for model in ("Anthbot Genie 1000", "Genie 600"):
        assert capabilities.supports_voice_volume(model, {}) is True
        assert capabilities.supports_voice_packages(model, {}) is True

    assert capabilities.supports_voice_volume("Unknown mower", {}) is False
    assert capabilities.supports_voice_packages("Unknown mower", {}) is False
    assert capabilities.supports_voice_volume(
        "Future mower", {"volume": 50}
    ) is True
    assert capabilities.supports_voice_packages(
        "Future mower", {"music_cfg": {"music_language": "English"}}
    ) is True


def test_voice_install_uses_confirmed_app_command_and_metadata() -> None:
    voice = _read(COMPONENT / "voice_packs.py")
    assert "/api/v1/voice/package/language" in voice
    assert "reports.mqbretrofithungary.online/api/anthbot/voice-packs" in voice
    assert 'cmd="voice_set"' in voice
    for field in (
        '"music_package"',
        '"english_name"',
        '"sex"',
        '"music_url"',
        '"music_md5"',
        '"category": "voice_pack"',
        '"version"',
    ):
        assert field in voice


def test_all_voice_entry_points_use_capability_guard() -> None:
    select = _read(COMPONENT / "select.py")
    number = _read(COMPONENT / "number.py")
    sensor = _read(COMPONENT / "sensor.py")
    coordinator = _read(COMPONENT / "coordinator.py")
    init = _read(COMPONENT / "__init__.py")

    assert "AnthbotVoicePackSelect" in select
    assert "supports_voice_packages(" in select
    assert 'description.key != "voice_volume_setting"' in number
    assert "supports_voice_volume(" in number
    assert 'description.key != "voice_volume"' in sensor
    assert "supports_voice_volume(" in sensor
    assert coordinator.count("supports_voice_volume(") >= 2
    assert "Voice volume is not supported by" in init


def test_map_card_hides_voice_controls_without_voice_entities() -> None:
    for path in (
        ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
        COMPONENT / "frontend" / "anthbot-map-card.js",
    ):
        card = _read(path)
        assert 'voicePack: ["voice_pack", "voice pack"]' in card
        assert 'if (this.getNumberEntity("voiceVolume"))' in card
        assert 'if (this.getSelectEntity("voicePack"))' in card
        assert 'this._hass.callService("select", "select_option"' in card
        fallback = card.split("hasSettingFallback(kind)", 1)[1].split(
            "async callSettingFallback", 1
        )[0]
        assert "voiceVolume" not in fallback
