from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "custom_components" / "anthbot_map" / "models" / "n8_voice_payload.py"
)

spec = importlib.util.spec_from_file_location("n8_voice_payload_test", MODULE_PATH)
assert spec is not None and spec.loader is not None
MODULE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = MODULE
spec.loader.exec_module(MODULE)


def _packet() -> dict[str, object]:
    return {
        "id": "English_girl",
        "english_name": "English",
        "sex": "girl",
        "md5": "0123456789abcdef",
        "version": 7,
        "vp_url": "voices/english_girl.zip",
    }


def test_voice_set_payload_matches_recovered_21516_shape() -> None:
    data = MODULE.build_voice_set_data(
        _packet(),
        presigned_url="https://example.invalid/signed-package",
    )
    assert data == {
        "music_package": "English_girl",
        "english_name": "English",
        "sex": "girl",
        "music_url": "https://example.invalid/signed-package",
        "music_md5": "0123456789abcdef",
        "category": "voice_pack",
        "version": 7,
    }
    assert MODULE.build_voice_set_command(
        _packet(),
        presigned_url="https://example.invalid/signed-package",
    ) == {"cmd": "voice_set", "data": data}


def test_voice_signed_url_request_keeps_filename_derivation_outside_helper() -> None:
    assert MODULE.build_voice_signed_url_request(
        serial_number="TEST-SN",
        filename="english_girl.zip",
    ) == {
        "sn": "TEST-SN",
        "category": "voice",
        "sub_category": "",
        "filename": "english_girl.zip",
    }


def test_voice_payload_rejects_missing_required_metadata() -> None:
    packet = _packet()
    del packet["md5"]
    try:
        MODULE.build_voice_set_data(packet, presigned_url="https://example.invalid/x")
    except ValueError as err:
        assert "md5" in str(err)
    else:
        raise AssertionError("voice payload accepted packet without md5")


def test_voice_payload_rejects_missing_signed_url() -> None:
    try:
        MODULE.build_voice_set_data(_packet(), presigned_url="")
    except ValueError:
        pass
    else:
        raise AssertionError("voice payload accepted empty presigned URL")
