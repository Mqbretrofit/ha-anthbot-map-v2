"""Pure helpers for the statically recovered N8/MGS03 voice-package payload.

These builders deliberately do not fetch packages, request signed URLs or publish
commands. Public Home Assistant voice-package selection remains disabled until a
real N8 validates package compatibility and report-side installation behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_REQUIRED_PACKET_FIELDS = (
    "id",
    "english_name",
    "sex",
    "md5",
    "version",
)


def voice_filename_from_vp_url(vp_url: str) -> str:
    """Mirror the 2.15.16 app's `getFilename(vp_url)` helper exactly.

    The app rejects null/empty input and otherwise returns the substring after
    the last `/`. No URL decoding or other normalization is applied there.
    """
    if not isinstance(vp_url, str) or not vp_url:
        raise ValueError("vp_url must be a non-empty string")
    return vp_url[vp_url.rfind("/") + 1 :]


def build_voice_set_data(
    packet: Mapping[str, Any],
    *,
    presigned_url: str,
) -> dict[str, Any]:
    """Return the exact 2.15.16 `voice_set.data` object."""
    if not isinstance(packet, Mapping):
        raise ValueError("voice packet must be a mapping")

    missing = [key for key in _REQUIRED_PACKET_FIELDS if key not in packet]
    if missing:
        raise ValueError(f"voice packet missing required fields: {', '.join(missing)}")

    if not isinstance(presigned_url, str) or not presigned_url.strip():
        raise ValueError("presigned_url must be a non-empty string")

    return {
        "music_package": packet["id"],
        "english_name": packet["english_name"],
        "sex": packet["sex"],
        "music_url": presigned_url,
        "music_md5": packet["md5"],
        "category": "voice_pack",
        "version": packet["version"],
    }


def build_voice_set_command(
    packet: Mapping[str, Any],
    *,
    presigned_url: str,
) -> dict[str, Any]:
    """Return the exact app-style `voice_set` command object."""
    return {
        "cmd": "voice_set",
        "data": build_voice_set_data(packet, presigned_url=presigned_url),
    }


def build_voice_signed_url_request(
    *,
    serial_number: str,
    vp_url: str,
) -> dict[str, str]:
    """Return the proven voice signed-URL request object."""
    if not isinstance(serial_number, str) or not serial_number.strip():
        raise ValueError("serial_number must be a non-empty string")
    return {
        "sn": serial_number,
        "category": "voice",
        "sub_category": "",
        "filename": voice_filename_from_vp_url(vp_url),
    }


__all__ = [
    "build_voice_set_command",
    "build_voice_set_data",
    "build_voice_signed_url_request",
    "voice_filename_from_vp_url",
]
