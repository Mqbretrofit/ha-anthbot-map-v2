"""Regression coverage for ANTHBOT firmware OTA support."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "anthbot_map"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_firmware_helpers():
    package_name = "anthbot_firmware_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(COMPONENT)]
    sys.modules[package_name] = package

    api = types.ModuleType(f"{package_name}.api")

    class AnthbotGenieApiError(Exception):
        pass

    api.AnthbotGenieApiError = AnthbotGenieApiError
    sys.modules[f"{package_name}.api"] = api

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.firmware_update",
        COMPONENT / "firmware_update.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{package_name}.firmware_update"] = module
    spec.loader.exec_module(module)
    return module


def test_new_ota_python_files_are_syntax_valid() -> None:
    for path in (
        COMPONENT / "api.py",
        COMPONENT / "firmware_update.py",
        COMPONENT / "update.py",
        COMPONENT / "switch.py",
    ):
        ast.parse(_read(path), filename=str(path))


def test_automatic_update_shadow_shapes() -> None:
    firmware = _load_firmware_helpers()
    assert firmware.automatic_update_value({"auto_upgrade": 0}) is False
    assert firmware.automatic_update_value({"auto_upgrade": 1}) is True
    assert firmware.automatic_update_value({"ota_params": {"auto": 0}}) is False
    assert firmware.automatic_update_value({"ota_params": {"auto": 1}}) is True
    assert firmware.automatic_update_value({}) is None


def test_manual_update_precondition_matches_app_rule() -> None:
    firmware = _load_firmware_helpers()
    assert firmware.update_precondition_error({"robot_sta": {"value": "idle"}}) is None
    assert firmware.update_precondition_error({"robot_sta": {"value": "charge"}}) is None
    error = firmware.update_precondition_error({"robot_sta": {"value": "mowing"}})
    assert error is not None
    assert "idle or charging" in error


def test_firmware_metadata_is_vendor_only_and_validated() -> None:
    firmware = _load_firmware_helpers()
    info = firmware.normalize_firmware_info(
        {
            "version": "1.17.2",
            "fw_url": "https://vendor.example/firmware/test.MowerPack",
            "md5": "6157b8627ebd06306e2eaad0c4744c78",
            "upgrade_mode": 3,
        }
    )
    assert info is not None
    assert info.version == "1.17.2"
    assert info.upgrade_mode == 3

    try:
        firmware.normalize_firmware_info(
            {
                "version": "1",
                "fw_url": "http://example.invalid/test.MowerPack",
                "md5": "6157b8627ebd06306e2eaad0c4744c78",
            }
        )
    except Exception:
        pass
    else:
        raise AssertionError("Non-HTTPS firmware URL must be rejected")


def test_cloud_calls_match_reconstructed_android_ota_protocol() -> None:
    api = _read(COMPONENT / "api.py")
    assert "/api/v1/device/latest/firmware" in api
    assert 'params={"sn": serial_number}' in api
    assert "/api/v1/device/v2/presigned_url" in api
    assert '"category": "firmware"' in api
    assert '"sub_category": ""' in api
    assert "/api/v1/device/v2/auto/upgrade" in api
    assert 'json={"sn": serial_number}' in api

    firmware = _read(COMPONENT / "firmware_update.py")
    assert 'cmd="ota_start"' in firmware
    for field in ('"category": "firmware"', '"version"', '"url"', '"md5"'):
        assert field in firmware


def test_ha_update_entity_exposes_install_progress_and_release_notes() -> None:
    update = _read(COMPONENT / "update.py")
    assert "UpdateDeviceClass.FIRMWARE" in update
    assert "UpdateEntityFeature.INSTALL" in update
    assert "UpdateEntityFeature.PROGRESS" in update
    assert "UpdateEntityFeature.RELEASE_NOTES" in update
    assert "def update_percentage" in update
    assert "async def async_install" in update

    init = _read(COMPONENT / "__init__.py")
    assert '"update"' in init


def test_auto_update_toggle_never_blindly_retries() -> None:
    switch = _read(COMPONENT / "switch.py")
    block = switch.split("class AnthbotAutomaticFirmwareUpdateSwitch", 1)[1]
    block = block.split("class AnthbotSwitchEntity", 1)[0]
    assert "if current == enabled:" in block
    assert block.count("async_toggle_auto_upgrade(") == 1
    assert "toggle was not confirmed" in block


def test_map_card_exposes_manual_and_automatic_ota_controls() -> None:
    for path in (
        ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
        COMPONENT / "frontend" / "anthbot-map-card.js",
    ):
        card = _read(path)
        assert 'firmware: ["firmware", "firmware_update"]' in card
        assert 'autoFirmwareUpdate: ["automatic_firmware_update"' in card
        assert 'this._hass.callService("update", "install"' in card
        assert 'this.getSwitchEntity("autoFirmwareUpdate")' in card
