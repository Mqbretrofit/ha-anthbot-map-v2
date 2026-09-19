"""ANTHBOT voice-package catalogue and installation helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import ClientError

from .api import AnthbotGenieApiError
from .models.capabilities import supports_voice_packages

_LOGGER = logging.getLogger(__name__)

# Community packs are intentionally served separately from ANTHBOT cloud.
# The endpoint may be empty/unavailable while the registry is being prepared;
# official ANTHBOT packs remain usable in that case.
COMMUNITY_VOICE_REGISTRY_URL = (
    "https://reports.mqbretrofithungary.online/api/anthbot/voice-packs"
)

# Verified community fallback. This keeps the already robot-tested Hungarian
# pack available while the external registry is being deployed or is offline.
_VERIFIED_COMMUNITY_FALLBACK = (
    {
        "id": "hu-girl-de-slot-3-v1.2.4",
        "language": "Magyar",
        "language_code": "hu",
        "english_name": "German",
        "sex": "girl",
        "music_package": 3,
        "version": "1.2.4",
        "music_url": (
            "https://ha.mqbretrofithungary.online/local/"
            "anthbot-map-v2/girl_de-1.2.4"
        ),
        "music_md5": "74e1955f019aa422d446a0d367232826",
        "size": 3117368,
        "models": ["Anthbot Genie 1000"],
    },
)



@dataclass(frozen=True, slots=True)
class VoicePack:
    """Normalized voice pack from ANTHBOT cloud or the community registry."""

    key: str
    label: str
    source: str
    music_package: str | int
    english_name: str
    sex: str
    version: str
    music_url: str
    music_md5: str
    language: str | None = None


def _first_text(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_scalar(record: dict[str, Any], *keys: str) -> str | int | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            if not isinstance(value, str) or value.strip():
                return value
    return None


def _iter_records(value: Any):
    if isinstance(value, dict):
        if any(key in value for key in ("vp_url", "music_url", "music_package")):
            yield value
        for item in value.values():
            yield from _iter_records(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_records(item)


def normalize_voice_pack(record: dict[str, Any], *, source: str) -> VoicePack | None:
    """Normalize known ANTHBOT/community metadata shapes."""
    music_url = _first_text(record, "music_url", "vp_url", "url", "download_url")
    music_md5 = _first_text(record, "music_md5", "vp_md5", "md5")
    music_package = _first_scalar(
        record, "music_package", "package_id", "voice_package_id", "id"
    )
    if music_url is None or music_md5 is None or music_package is None:
        return None

    english_name = _first_text(
        record, "english_name", "englishName", "language_en", "language"
    ) or "Voice"
    language = _first_text(record, "language", "language_name", "name")
    sex = _first_text(record, "sex", "gender") or "girl"
    version = _first_text(record, "version", "vp_version") or "0"
    display_name = language or english_name
    source_label = "ANTHBOT" if source == "anthbot" else "Community"
    label = f"{display_name} · {source_label}"
    key = f"{source}:{music_package}:{english_name}:{sex}:{version}"

    return VoicePack(
        key=key,
        label=label,
        source=source,
        music_package=music_package,
        english_name=english_name,
        sex=sex,
        version=version,
        music_url=music_url,
        music_md5=music_md5,
        language=language,
    )


async def async_get_official_voice_packs(account_client: Any) -> list[VoicePack]:
    """Fetch the official ANTHBOT voice catalogue used by the app."""
    account_client._require_token()
    url = f"https://{account_client._host}/api/v1/voice/package/language"
    try:
        async with account_client._session.get(
            url,
            headers=account_client._auth_headers,
            timeout=15,
        ) as response:
            if response.status != 200:
                body = await response.text()
                raise AnthbotGenieApiError(
                    f"Voice catalogue failed ({response.status}): {body[:300]}"
                )
            payload = await response.json(content_type=None)
    except ClientError as err:
        raise AnthbotGenieApiError(f"Voice catalogue network error: {err}") from err
    except TimeoutError as err:
        raise AnthbotGenieApiError("Voice catalogue request timed out") from err

    if not isinstance(payload, dict):
        raise AnthbotGenieApiError("Invalid voice catalogue payload")
    if payload.get("code") not in (None, 0):
        raise AnthbotGenieApiError(
            f"Voice catalogue returned code={payload.get('code')}"
        )

    packs: list[VoicePack] = []
    seen: set[str] = set()
    for record in _iter_records(payload.get("data", payload)):
        pack = normalize_voice_pack(record, source="anthbot")
        if pack is not None and pack.key not in seen:
            packs.append(pack)
            seen.add(pack.key)
    return packs


def _verified_community_fallback() -> list[VoicePack]:
    """Return community packs that have already passed a real mower install."""
    return [
        pack
        for record in _VERIFIED_COMMUNITY_FALLBACK
        if (pack := normalize_voice_pack(record, source="community")) is not None
    ]


async def async_get_community_voice_packs(
    session: Any,
    *,
    use_fallback: bool = True,
) -> list[VoicePack] | None:
    """Fetch community voice packs.

    Startup may use the verified Hungarian fallback. Periodic refreshes can
    disable fallback so a temporary network/server failure never replaces a
    previously loaded dynamic catalogue with only the fallback entry.
    """
    try:
        async with session.get(COMMUNITY_VOICE_REGISTRY_URL, timeout=15) as response:
            if response.status != 200:
                _LOGGER.debug(
                    "Community voice registry unavailable: HTTP %s", response.status
                )
                return _verified_community_fallback() if use_fallback else None
            payload = await response.json(content_type=None)
    except (ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Community voice registry unavailable: %s", err)
        return _verified_community_fallback() if use_fallback else None

    packs: list[VoicePack] = []
    seen: set[str] = set()
    for record in _iter_records(payload):
        pack = normalize_voice_pack(record, source="community")
        if pack is not None and pack.key not in seen:
            packs.append(pack)
            seen.add(pack.key)

    if not packs and use_fallback:
        return _verified_community_fallback()
    return packs


async def async_get_voice_packs(coordinator: Any) -> list[VoicePack]:
    """Return official + community voice packs for a voice-capable mower."""
    if not supports_voice_packages(
        getattr(coordinator.device, "model", None),
        coordinator.reported_state,
    ):
        return []

    try:
        official = await async_get_official_voice_packs(coordinator.account_client)
    except AnthbotGenieApiError as err:
        _LOGGER.debug(
            "Official ANTHBOT voice catalogue unavailable for %s: %s",
            coordinator.client.serial_number,
            err,
        )
        official = []

    community = await async_get_community_voice_packs(
        coordinator.account_client._session
    )
    return official + (community or [])


def installed_voice_identity(state: dict[str, Any]) -> tuple[Any, str | None, str | None]:
    """Return installed package id, displayed name and version from live state."""
    music_cfg = state.get("music_cfg")
    voice_status = state.get("voice_status")
    cfg = music_cfg if isinstance(music_cfg, dict) else {}
    status = voice_status if isinstance(voice_status, dict) else {}

    package_id = (
        cfg.get("music_package")
        if cfg.get("music_package") is not None
        else status.get("music_package")
    )
    name = (
        _first_text(status, "name", "english_name", "language")
        or _first_text(cfg, "music_language", "english_name", "language")
    )
    version = _first_text(status, "version") or _first_text(cfg, "version")
    return package_id, name, version


async def async_install_voice_pack(coordinator: Any, pack: VoicePack) -> None:
    """Install a selected voice pack through the app-confirmed voice_set command."""
    model = getattr(coordinator.device, "model", None)
    if not supports_voice_packages(model, coordinator.reported_state):
        raise AnthbotGenieApiError(
            f"Voice packages are not supported by {model or 'this mower'}"
        )

    data = {
        "music_package": pack.music_package,
        "english_name": pack.english_name,
        "sex": pack.sex,
        "music_url": pack.music_url,
        "music_md5": pack.music_md5,
        "category": "voice_pack",
        "version": pack.version,
    }
    await coordinator.client.async_publish_service_command(
        cmd="voice_set",
        data=data,
    )
