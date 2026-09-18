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


def test_voice_capability_is_hard_disabled_for_m9_family() -> None:
    capabilities = _load_capabilities()
    assert capabilities.supports_voice("Anthbot M9", {}) is False
    assert capabilities.supports_voice("Anthbot M9 Pro", {}) is False
    # A misleading cloud field must never override the known hardware limit.
    assert capabilities.supports_voice(
        "Anthbot M9 Pro", {"voice_status": {"name": "English"}, "volume": 50}
    ) is False


def test_genie_voice_is_enabled_and_unknown_models_fail_closed() -> None:
    capabilities = _load_capabilities()
    assert capabilities.supports_voice("Anthbot Genie 1000", {}) is True
    assert capabilities.supports_voice("Genie 600", {}) is True
    assert capabilities.supports_voice("Unknown mower", {}) is False
    assert capabilities.supports_voice(
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
    assert "supports_voice(" in select
    assert 'description.key != "voice_volume_setting"' in number
    assert "supports_voice(" in number
    assert 'description.key != "voice_volume"' in sensor
    assert "supports_voice(" in sensor
    assert coordinator.count("supports_voice(") >= 2
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
