"""Regression tests for the app-compatible ANTHBOT OTA path."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components" / "anthbot_map"


def _source(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


def test_latest_firmware_request_matches_android_app() -> None:
    source = _source("api.py")
    assert '"/api/v1/device/latest/firmware"' in source
    assert 'params={"sn": serial_number}' in source
    firmware_block = source[
        source.index("async def async_get_latest_firmware"):
        source.index("async def async_get_presigned_download_url")
    ]
    assert "self._session.get(" in firmware_block
    assert "version/fw_url" in firmware_block


def test_manual_ota_payload_is_exact_android_shape() -> None:
    source = _source("firmware_update.py")
    start = source.index("async def async_start_vendor_firmware_update")
    block = source[start:]

    assert 'cmd="ota_start"' in block
    assert "async_get_presigned_download_url" in block
    assert 'category="firmware"' in block
    assert 'sub_category=""' in block
    assert '"category": "firmware"' in block
    assert '"version": firmware.version' in block
    assert '"url": presigned_url' in block
    assert '"md5": firmware.md5' in block
    assert '"url": firmware.fw_url' not in block



def test_firmware_presigned_url_request_matches_android_app() -> None:
    source = _source("api.py")
    start = source.index("async def async_get_presigned_download_url")
    end = source.index("async def async_toggle_auto_upgrade", start)
    block = source[start:end]

    assert '"/api/v1/device/v2/presigned_url"' in block
    assert '"sn": serial_number' in block
    assert '"category": category' in block
    assert '"sub_category": sub_category' in block
    assert '"filename": filename' in block
    assert '"verification_token": self.build_verification_token(serial_number)' in block
    assert "self._session.get(" in block


def test_automatic_ota_toggle_matches_android_app() -> None:
    source = _source("api.py")
    start = source.index("async def async_toggle_auto_upgrade")
    end = source.index("async def async_get_mowing_records", start)
    block = source[start:end]

    assert '"/api/v1/device/v2/auto/upgrade"' in block
    assert "self._session.post(" in block
    assert 'json={"sn": serial_number}' in block


def test_home_assistant_update_platform_is_registered() -> None:
    init_source = _source("__init__.py")
    update_source = _source("update.py")

    assert '"update",' in init_source
    assert "class AnthbotFirmwareUpdateEntity" in update_source
    assert "UpdateDeviceClass.FIRMWARE" in update_source
    assert "UpdateEntityFeature.INSTALL" in update_source
    assert "UpdateEntityFeature.PROGRESS" in update_source


def test_only_vendor_offered_firmware_can_be_installed() -> None:
    source = _source("update.py")
    assert "async_get_latest_firmware" in source
    assert "Only the firmware version currently offered by ANTHBOT" in source
    assert "async_start_vendor_firmware_update" in source
