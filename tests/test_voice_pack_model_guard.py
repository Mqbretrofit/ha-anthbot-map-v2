"""Regression tests for voice-pack model gating."""

from custom_components.anthbot_map.models.capabilities import (
    supports_voice_packages,
    supports_voice_volume,
)


def test_m5_never_exposes_voice_pack_even_with_cloud_voice_fields():
    for model in ("M5", "M5 Pro", "ANTHBOT M5"):
        for state in ({}, {"music_cfg": {}}, {"voice_status": {}}, {"music_cfg": {"id": 1}}):
            assert not supports_voice_packages(model, state)


def test_m9_models_remain_excluded_from_spoken_voice_packs():
    for model in ("M9", "M9 Pro"):
        assert not supports_voice_packages(model, {"voice_status": {}})
        assert supports_voice_volume(model)


def test_genie_voice_packs_remain_available():
    assert supports_voice_packages("Genie 1000", {})
    assert supports_voice_packages("ANTHBOT Genie", {"music_cfg": {}})
