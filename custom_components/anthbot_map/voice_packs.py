"""ANTHBOT voice-package catalogue and installation helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from typing import Any

from aiohttp import ClientError

from .api import AnthbotGenieApiError
from .models.capabilities import supports_voice_packages

_LOGGER = logging.getLogger(__name__)

_ROBOT_LANGUAGE_ALIASES: dict[str, str] = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "ru": "Russian",
    "es": "Spanish",
}
_ROBOT_SEX_ALIASES: dict[str, str] = {
    "girl": "girl",
    "female": "girl",
    "woman": "girl",
    "boy": "boy",
    "male": "boy",
    "man": "boy",
}


def normalize_reported_voice_name(name: str | None) -> tuple[str | None, str | None]:
    """Normalize mower voice IDs such as girl_en/girl_de to catalogue identity."""
    if not isinstance(name, str) or not name.strip():
        return None, None

    raw = name.strip()
    folded = raw.casefold()
    for english_name in _ROBOT_LANGUAGE_ALIASES.values():
        if folded == english_name.casefold():
            return english_name, None

    tokens = [
        token for token in folded.replace("-", "_").split("_")
        if token
    ]
    language: str | None = None
    sex: str | None = None
    language_names = {
        english_name.casefold(): english_name
        for english_name in _ROBOT_LANGUAGE_ALIASES.values()
    }
    for token in tokens:
        if token in _ROBOT_LANGUAGE_ALIASES:
            language = _ROBOT_LANGUAGE_ALIASES[token]
        elif token in language_names:
            # Some Genie firmware reports full identifiers such as
            # "German_girl" instead of the shorter "girl_de".
            language = language_names[token]
        if token in _ROBOT_SEX_ALIASES:
            sex = _ROBOT_SEX_ALIASES[token]

    return language, sex

# Community packs are intentionally served separately from ANTHBOT cloud.
# The endpoint may be empty/unavailable while the registry is being prepared;
# official ANTHBOT packs remain usable in that case.
COMMUNITY_VOICE_REGISTRY_URL = (
    "https://reports.mqbretrofithungary.online/api/anthbot/store/voice-packs"
)
OFFICIAL_VOICE_CACHE_URL = (
    "https://reports.mqbretrofithungary.online/api/anthbot/voice-packs/cache-official"
)
VOICE_STORE_PAIR_URL = (
    "https://reports.mqbretrofithungary.online/api/anthbot/store/client/pair"
)
VOICE_STORE_ENTITLEMENTS_URL = (
    "https://reports.mqbretrofithungary.online/api/anthbot/store/client/entitlements"
)

# Every custom/Community voice is installed into the same Genie factory slot.
# These values describe the technical mower slot, not the human speaker.
COMMUNITY_TECHNICAL_LANGUAGE = "German"
COMMUNITY_TECHNICAL_SEX = "girl"
COMMUNITY_TECHNICAL_SLOT = "German_girl"

# Verified community fallback. This keeps the already robot-tested Hungarian
# pack available while the external registry is being deployed or is offline.
_VERIFIED_COMMUNITY_FALLBACK = (
    {
        "id": "hu-girl-de-slot-3-v1.2.4",
        "language": "Magyar",
        "language_code": "hu",
        "community_id": "hu_noemi_standard",
        "variant_id": "noemi_standard",
        "variant_name": "Noémi (női) · Standard",
        "voice_gender": "female",
        "technical_slot": "German_girl",
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
    community_id: str | None = None
    variant_id: str | None = None
    variant_name: str | None = None
    voice_gender: str | None = None
    technical_slot: str | None = None
    access: str = "free"
    price_amount: int | None = None
    currency: str | None = None
    locked: bool = False


def _technical_voice_slot(name: object, sex: object) -> str | None:
    """Return the mower's technical voice slot name."""
    if not isinstance(name, str) or not name.strip():
        return None
    if not isinstance(sex, str) or not sex.strip():
        return None
    return f"{name.strip()}_{sex.strip()}".casefold()


def voice_pack_verification_key(pack: VoicePack) -> str:
    """Return the robot-visible identity: technical slot + package version."""
    slot = _technical_voice_slot(pack.english_name, pack.sex)
    if slot is None:
        return ""
    return f"{slot}|{pack.version.strip().casefold()}"


def reported_voice_verification_key(
    name: object,
    sex: object,
    version: object,
) -> str | None:
    """Build technical slot + version from mower-reported metadata."""
    slot = _technical_voice_slot(name, sex)
    if slot is None:
        return None
    if not isinstance(version, str) or not version.strip():
        return None
    return f"{slot}|{version.strip().casefold()}"


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
    access = str(record.get("access") or "free").strip().casefold()
    if access not in {"free", "paid"}:
        access = "free"

    music_url = _first_text(record, "music_url", "vp_url", "url", "download_url")
    music_md5 = _first_text(record, "music_md5", "vp_md5", "md5")
    music_package = _first_scalar(
        record, "music_package", "package_id", "voice_package_id", "id"
    )
    locked = source == "community" and access == "paid" and music_url is None
    if music_md5 is None or music_package is None:
        return None
    if music_url is None and not locked:
        return None
    if music_url is None:
        music_url = ""

    english_name = _first_text(
        record, "english_name", "englishName", "language_en", "language"
    ) or "Voice"
    language = _first_text(record, "language", "language_name", "name")
    community_id = _first_text(record, "community_id", "community_voice_id")
    variant_id = _first_text(record, "variant_id", "variant", "voice_variant")
    variant_name = _first_text(
        record, "variant_name", "variant_label", "voice_variant_name"
    )
    voice_gender = _first_text(
        record, "voice_gender", "speaker_gender", "human_gender"
    )
    technical_slot = _first_text(record, "technical_slot", "robot_slot")
    sex = _first_text(record, "sex", "gender") or "girl"
    if source == "community":
        # All custom voices deliberately reuse the same Genie factory slot.
        # voice_gender describes the real speaker; sex=girl only addresses
        # the mower's German_girl slot and must never be used as speaker gender.
        english_name = COMMUNITY_TECHNICAL_LANGUAGE
        sex = COMMUNITY_TECHNICAL_SEX
        technical_slot = COMMUNITY_TECHNICAL_SLOT
        if not community_id:
            language_code = _first_text(record, "language_code", "locale") or "community"
            community_id = f"{language_code}_{variant_id or 'default'}".casefold()
    version = _first_text(record, "version", "vp_version") or "0"
    display_name = language or english_name
    if source == "community" and variant_name:
        display_name = f"{display_name} – {variant_name}"
    source_label = "ANTHBOT" if source == "anthbot" else "Community"
    label = f"{display_name} · {source_label}"
    if locked:
        price_raw = record.get("price_amount")
        try:
            display_price = max(0, int(price_raw or 0))
        except (TypeError, ValueError):
            display_price = 0
        currency_raw = _first_text(record, "currency") or "eur"
        if display_price > 0:
            label = (
                f"🔒 {label} · {display_price / 100:.2f} "
                f"{currency_raw.upper()}"
            )
        else:
            label = f"🔒 {label} · Fizetős"
    key = (
        f"{source}:{community_id or variant_id or ''}:{music_package}:"
        f"{english_name}:{sex}:{version}"
    )

    price_raw = record.get("price_amount")
    try:
        price_amount = int(price_raw) if price_raw is not None else None
    except (TypeError, ValueError):
        price_amount = None
    currency = _first_text(record, "currency")
    if currency is not None:
        currency = currency.casefold()

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
        community_id=community_id,
        variant_id=variant_id,
        variant_name=variant_name,
        voice_gender=voice_gender,
        technical_slot=technical_slot,
        access=access,
        price_amount=price_amount,
        currency=currency,
        locked=locked,
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


async def async_create_voice_store_pairing(
    session: Any,
    client_token: str,
) -> tuple[str | None, str | None]:
    """Return a temporary browser URL linked to one anonymous Map client."""
    try:
        async with session.post(
            VOICE_STORE_PAIR_URL,
            json={"client_token": client_token},
            timeout=15,
        ) as response:
            if response.status != 200:
                body = await response.text()
                return None, f"pair HTTP {response.status}: {body[:180]}"
            payload = await response.json(content_type=None)
    except (ClientError, TimeoutError, ValueError) as err:
        return None, f"pair request failed: {err}"

    if not isinstance(payload, dict):
        return None, "pair returned invalid payload"
    store_url = payload.get("store_url")
    if not isinstance(store_url, str) or not store_url.startswith("https://"):
        return None, "pair returned invalid store_url"
    return store_url, None


async def async_get_purchased_voice_packs(
    session: Any,
    client_token: str,
) -> list[VoicePack] | None:
    """Return paid Community packs owned by one anonymous Map client.

    None means the entitlement service could not be reached, so callers should
    keep the last known paid catalogue instead of dropping purchased voices.
    """
    try:
        async with session.post(
            VOICE_STORE_ENTITLEMENTS_URL,
            json={"client_token": client_token},
            timeout=15,
        ) as response:
            if response.status != 200:
                _LOGGER.debug(
                    "Voice store entitlement lookup unavailable: HTTP %s",
                    response.status,
                )
                return None
            payload = await response.json(content_type=None)
    except (ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Voice store entitlement lookup unavailable: %s", err)
        return None

    if not isinstance(payload, dict):
        return None

    records = payload.get("packs")
    if not isinstance(records, list):
        return []

    packs: list[VoicePack] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        pack = normalize_voice_pack(record, source="community")
        if pack is not None and pack.key not in seen:
            packs.append(pack)
            seen.add(pack.key)
    return packs


async def async_cache_official_voice_pack(
    session: Any,
    pack: VoicePack,
) -> tuple[VoicePack, bool, str | None]:
    """Mirror one official ANTHBOT pack behind the stable Reporting Server URL."""
    if pack.source != "anthbot":
        return pack, False, None

    try:
        async with session.post(
            OFFICIAL_VOICE_CACHE_URL,
            json={
                "source_url": pack.music_url,
                "music_md5": pack.music_md5,
            },
            timeout=45,
        ) as response:
            if response.status != 200:
                body = await response.text()
                return (
                    pack,
                    False,
                    f"cache HTTP {response.status}: {body[:180]}",
                )
            payload = await response.json(content_type=None)
    except (ClientError, TimeoutError, ValueError) as err:
        return pack, False, f"cache request failed: {err}"

    if not isinstance(payload, dict):
        return pack, False, "cache returned invalid payload"
    cached_url = payload.get("music_url")
    cached_md5 = payload.get("music_md5")
    if not isinstance(cached_url, str) or not cached_url.startswith("https://"):
        return pack, False, "cache returned invalid music_url"
    if (
        not isinstance(cached_md5, str)
        or cached_md5.casefold() != pack.music_md5.casefold()
    ):
        return pack, False, "cache returned mismatching MD5"

    return replace(pack, music_url=cached_url), True, None


def merge_community_voice_packs(
    catalogue: list[VoicePack],
    purchased: list[VoicePack],
) -> list[VoicePack]:
    """Merge public catalogue with entitlements, purchased packs winning by stable ID."""
    owned_by_id = {
        pack.community_id: pack
        for pack in purchased
        if pack.community_id
    }
    merged: list[VoicePack] = []
    seen: set[str] = set()
    for pack in catalogue:
        stable_id = pack.community_id or pack.key
        replacement = owned_by_id.get(pack.community_id) if pack.community_id else None
        chosen = replacement or pack
        if stable_id in seen:
            continue
        merged.append(chosen)
        seen.add(stable_id)
    for pack in purchased:
        stable_id = pack.community_id or pack.key
        if stable_id in seen:
            continue
        merged.append(pack)
        seen.add(stable_id)
    return merged


async def async_get_voice_packs(
    coordinator: Any,
    *,
    store_client_token: str | None = None,
) -> list[VoicePack]:
    """Return official, free Community and purchased Community voice packs."""
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
    purchased: list[VoicePack] = []
    if store_client_token:
        owned = await async_get_purchased_voice_packs(
            coordinator.account_client._session,
            store_client_token,
        )
        if owned is not None:
            purchased = owned
    return official + merge_community_voice_packs(community or [], purchased)


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
    # music_cfg.music_language is the active slot. voice_status.name is the
    # last install/report operation and can remain stale after the active slot
    # changes, so it must not override music_language.
    name = (
        _first_text(cfg, "music_language", "english_name", "language")
        or _first_text(status, "name", "english_name", "language")
    )
    version = None
    if isinstance(name, str) and name:
        slot_version = cfg.get(name)
        if isinstance(slot_version, (str, int, float)) and not isinstance(
            slot_version, bool
        ):
            version = str(slot_version).strip() or None
    if version is None:
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
