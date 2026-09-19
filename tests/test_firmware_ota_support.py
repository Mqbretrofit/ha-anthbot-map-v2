"""Regression coverage for ANTHBOT firmware OTA support."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest


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


class FirmwareOtaSupportTests(unittest.TestCase):
    def test_new_ota_python_files_are_syntax_valid(self) -> None:
        for path in (
            COMPONENT / "api.py",
            COMPONENT / "firmware_update.py",
            COMPONENT / "update.py",
            COMPONENT / "switch.py",
        ):
            ast.parse(_read(path), filename=str(path))

    def test_automatic_update_shadow_shapes(self) -> None:
        firmware = _load_firmware_helpers()
        self.assertIs(firmware.automatic_update_value({"auto_upgrade": 0}), False)
        self.assertIs(firmware.automatic_update_value({"auto_upgrade": 1}), True)
        self.assertIs(
            firmware.automatic_update_value({"ota_params": {"auto": 0}}), False
        )
        self.assertIs(
            firmware.automatic_update_value({"ota_params": {"auto": 1}}), True
        )
        self.assertIsNone(firmware.automatic_update_value({}))

    def test_manual_update_blocks_only_an_already_active_ota(self) -> None:
        firmware = _load_firmware_helpers()
        self.assertFalse(firmware.ota_in_progress({}))
        self.assertTrue(
            firmware.ota_in_progress(
                {"ota_status": {"ota_state": "downloading", "ota_progress": 25}}
            )
        )
        # Do not invent model-specific robot-state restrictions that are not
        # part of the recovered Android 2.15.16 OTA command path.
        self.assertNotIn("update_precondition_error", firmware.__dict__)

    def test_firmware_metadata_is_vendor_only_and_validated(self) -> None:
        firmware = _load_firmware_helpers()
        info = firmware.normalize_firmware_info(
            {
                "version": "1.17.2",
                "fw_url": "https://vendor.example/firmware/test.MowerPack",
                "md5": "6157b8627ebd06306e2eaad0c4744c78",
                "upgrade_mode": 3,
            }
        )
        self.assertIsNotNone(info)
        self.assertEqual("1.17.2", info.version)
        self.assertEqual(3, info.upgrade_mode)

        with self.assertRaises(Exception):
            firmware.normalize_firmware_info(
                {
                    "version": "1",
                    "fw_url": "http://example.invalid/test.MowerPack",
                    "md5": "6157b8627ebd06306e2eaad0c4744c78",
                }
            )

    def test_cloud_calls_match_android_21516_ota_protocol(self) -> None:
        api = _read(COMPONENT / "api.py")
        self.assertIn("/api/v1/device/latest/firmware", api)
        self.assertIn('params={"sn": serial_number}', api)
        self.assertIn("/api/v1/device/v2/auto/upgrade", api)
        self.assertIn('json={"sn": serial_number}', api)
        self.assertIn("async_get_presigned_download_url", api)
        presigned = api.split("async def async_get_presigned_download_url", 1)[1]
        presigned = presigned.split("async def async_toggle_auto_upgrade", 1)[0]
        self.assertIn("/api/v1/device/v2/presigned_url", presigned)
        for field in (
            '"sn": serial_number',
            '"category": category',
            '"sub_category": sub_category',
            '"filename": filename',
            '"verification_token": self.build_verification_token(serial_number)',
        ):
            self.assertIn(field, presigned)

        firmware = _read(COMPONENT / "firmware_update.py")
        block = firmware.split("async def async_start_vendor_firmware_update", 1)[1]
        self.assertIn('cmd="ota_start"', block)
        self.assertIn('category="firmware"', block)
        self.assertIn('sub_category=""', block)
        self.assertIn('"category": "firmware"', block)
        self.assertIn('"version": firmware.version', block)
        self.assertIn('"url": presigned_url', block)
        self.assertIn('"md5": firmware.md5', block)
        self.assertNotIn('"url": firmware.fw_url', block)

    def test_live_shadow_firmware_and_ota_shapes_are_supported(self) -> None:
        firmware = _load_firmware_helpers()
        state = {
            "fw_version": {"system_version": "1.17.2"},
            "ota_status": {"ota_state": "downloading", "ota_progress": 42},
        }
        self.assertEqual("1.17.2", firmware.installed_firmware_version(state))
        self.assertEqual(("downloading", 42), firmware.ota_status(state))
        self.assertEqual(("installing", 67), firmware.ota_status({
            "ota_state": "installing",
            "ota_progress": 67,
        }))

    def test_ha_update_entity_exposes_install_progress_and_release_notes(self) -> None:
        update = _read(COMPONENT / "update.py")
        self.assertIn("UpdateDeviceClass.FIRMWARE", update)
        self.assertIn("UpdateEntityFeature.INSTALL", update)
        self.assertIn("UpdateEntityFeature.PROGRESS", update)
        self.assertIn("UpdateEntityFeature.RELEASE_NOTES", update)
        self.assertIn("def update_percentage", update)
        self.assertIn("async def async_install", update)

        init = _read(COMPONENT / "__init__.py")
        self.assertIn('"update"', init)

    def test_auto_update_toggle_never_blindly_retries(self) -> None:
        switch = _read(COMPONENT / "switch.py")
        block = switch.split("class AnthbotAutomaticFirmwareUpdateSwitch", 1)[1]
        block = block.split("class AnthbotSwitchEntity", 1)[0]
        self.assertIn("if current == enabled:", block)
        self.assertEqual(1, block.count("async_toggle_auto_upgrade("))
        self.assertIn("toggle was not confirmed", block)

    def test_map_card_exposes_manual_and_automatic_ota_controls(self) -> None:
        for path in (
            ROOT / "www" / "anthbot-map" / "anthbot-map-card.js",
            COMPONENT / "frontend" / "anthbot-map-card.js",
        ):
            card = _read(path)
            self.assertIn('firmware: ["firmware", "firmware_update"]', card)
            self.assertIn(
                'autoFirmwareUpdate: ["automatic_firmware_update"', card
            )
            self.assertIn(
                'this._hass.callService("update", "install"', card
            )
            self.assertIn(
                'this.getSwitchEntity("autoFirmwareUpdate")', card
            )


if __name__ == "__main__":
    unittest.main()
