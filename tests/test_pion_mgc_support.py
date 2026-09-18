"""Regression coverage for isolated ANTHBOT Pion / MGC support."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "anthbot_map"
MODELS = INTEGRATION / "models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_base():
    path = MODELS / "base.py"
    spec = importlib.util.spec_from_file_location("anthbot_model_base_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mgc_and_pion_have_isolated_model_family() -> None:
    base = _load_base()
    for model in (
        "Anthbot MGC500",
        "Anthbot MGC750",
        "Anthbot MGC1000",
        "Pion 500",
        "Pion 750",
        "Pion 1000",
    ):
        assert base.model_family(model) == "pion"

    # Existing family routing must stay unchanged.
    assert base.model_family("Anthbot Genie 1000") == "genie"
    assert base.model_family("Anthbot M5") == "m5"
    assert base.model_family("Anthbot M9") == "m9"
    assert base.model_family("Anthbot M9 Pro") == "m9_pro"
    assert base.model_family("Anthbot N8") == "n8"


def test_pion_adapter_is_isolated_and_installed() -> None:
    boundary = _read(MODELS / "pion.py")
    status = _read(MODELS / "pion_status.py")
    common = _read(MODELS / "m_series_common.py")

    assert 'MODEL_FAMILY = "pion"' in boundary
    assert 'return model_family(model) == "pion"' in status
    assert 'state["_pion"] = snapshot' in status
    assert "install_pion_status_support()" in common

    # The first adapter is deliberately read/normalize-only.
    assert "async_publish_service_command" not in status


def test_pion_snapshot_contains_only_confirmed_mgc_fields() -> None:
    status = _read(MODELS / "pion_status.py")
    for field in (
        '"cutter_height"',
        '"mowing_progress"',
        '"mowing_area"',
        '"mow_direction"',
        '"rainer_ctl"',
        '"rainer_effect"',
        '"near_chg_mow_ctl"',
        '"rssi"',
        '"sta_ip_addr"',
        '"maptime"',
        '"curpath"',
        '"breakpoint"',
        '"fw_version"',
    ):
        assert field in status


def test_pion_uses_native_start_wake_path_without_genie_app_state() -> None:
    commands = _read(INTEGRATION / "commands.py")
    assert 'model_family(getattr(coordinator.device, "model", "")) == "pion"' in commands
    assert "native_app_model = m_series or n8 or pion" in commands
    assert "if not pion:" in commands
    assert 'cmd="app_state", data=app_state' in commands
    assert 'cmd="mow_start", data=1' in commands


def test_pion_sensor_fallbacks_are_namespaced() -> None:
    sensors = _read(INTEGRATION / "sensor.py")
    assert '_safe_get(data, "_pion", "cutter_height")' in sensors
    assert '_safe_get(data, "_pion", "mowing_progress")' in sensors
    assert '_safe_get(data, "_pion", "mowing_area")' in sensors
