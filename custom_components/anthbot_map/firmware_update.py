"""Vendor firmware update helpers for ANTHBOT mowers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .api import AnthbotGenieApiError

_MD5_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_ALLOWED_UPDATE_STATES = frozenset(
    {"idle", "charge", "charging", "standby", "docked", "dock"}
)
_FINISHED_OTA_STATES = frozenset(
    {"", "idle", "success", "succeeded", "complete", "completed", "done"}
)
_FAILED_OTA_STATES = frozenset({"fail", "failed", "error"})


@dataclass(frozen=True, slots=True)
class FirmwareInfo:
    """Normalized official ANTHBOT firmware metadata."""

    version: str
    fw_url: str
    md5: str
    upgrade_mode: int | str | None = None
    firmware_id: int | str | None = None
    description: str | None = None


def normalize_firmware_info(value: dict[str, Any] | None) -> FirmwareInfo | None:
    """Validate and normalize firmware metadata returned by ANTHBOT."""
    if not isinstance(value, dict):
        return None
    version = value.get("version")
    fw_url = value.get("fw_url")
    md5 = value.get("md5")
    if not all(isinstance(item, str) and item.strip() for item in (version, fw_url, md5)):
        return None
    version = version.strip()
    fw_url = fw_url.strip()
    md5 = md5.strip().lower()
    if not fw_url.lower().startswith("https://"):
        raise AnthbotGenieApiError("Firmware URL is not HTTPS")
    if not _MD5_RE.fullmatch(md5):
        raise AnthbotGenieApiError("Firmware metadata contains an invalid MD5")
    description = value.get("description")
    return FirmwareInfo(
        version=version,
        fw_url=fw_url,
        md5=md5,
        upgrade_mode=value.get("upgrade_mode"),
        firmware_id=value.get("firmware_id"),
        description=description.strip() if isinstance(description, str) and description.strip() else None,
    )


def _unwrap(value: Any) -> Any:
    """Unwrap common ANTHBOT value envelopes."""
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def installed_firmware_version(state: dict[str, Any]) -> str | None:
    """Return the mower's currently reported firmware version."""
    for key in ("fw_version", "firmware_version", "system_version"):
        value = _unwrap(state.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for nested_key in (
                "system_version",
                "image_version",
                "version",
                "app_version",
            ):
                nested = _unwrap(value.get(nested_key))
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return None


def automatic_update_value(state: dict[str, Any]) -> bool | None:
    """Read the automatic firmware update setting from known shadow shapes."""
    value = _unwrap(state.get("auto_upgrade"))
    if value is None:
        ota_params = state.get("ota_params")
        if isinstance(ota_params, dict):
            value = _unwrap(ota_params.get("auto"))
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value) == 1
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "enabled", "enable"}:
            return True
        if normalized in {"0", "false", "off", "disabled", "disable"}:
            return False
    return None


def ota_status(state: dict[str, Any]) -> tuple[str, int | float | None]:
    """Return normalized OTA state and progress."""
    raw = state.get("ota_status")
    status = raw if isinstance(raw, dict) else {}
    state_value = _unwrap(status.get("ota_state"))
    state_text = str(state_value or "").strip().lower()

    progress_value = _unwrap(status.get("ota_progress"))
    progress: int | float | None = None
    if isinstance(progress_value, (int, float)) and not isinstance(progress_value, bool):
        progress = max(0, min(100, progress_value))
    elif isinstance(progress_value, str):
        try:
            progress = max(0, min(100, float(progress_value)))
        except ValueError:
            progress = None
    return state_text, progress


def ota_in_progress(state: dict[str, Any]) -> bool:
    """Return whether the shadow indicates an active firmware update."""
    state_text, progress = ota_status(state)
    if progress is not None and 0 < progress < 100:
        return True
    if state_text in _FAILED_OTA_STATES or state_text in _FINISHED_OTA_STATES:
        return False
    return bool(state_text)


def update_precondition_error(state: dict[str, Any]) -> str | None:
    """Return a proven app-side OTA precondition failure, if clearly known."""
    if ota_in_progress(state):
        return "A firmware update is already in progress"

    status_value: Any = None
    for key in ("robot_sta", "mower_status", "robot_status", "mode"):
        candidate = _unwrap(state.get(key))
        if candidate not in (None, ""):
            status_value = candidate
            break

    # Only block when the mower gives us a textual state we understand.
    # Unknown/model-specific numeric states are left to the mower's own safety
    # checks rather than guessing their meaning.
    if isinstance(status_value, str):
        normalized = status_value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized not in _ALLOWED_UPDATE_STATES:
            return "Firmware update is allowed only while the mower is idle or charging"
    return None


async def async_start_vendor_firmware_update(
    coordinator: Any,
    firmware: FirmwareInfo,
) -> None:
    """Start the official app-compatible OTA pipeline."""
    error = update_precondition_error(coordinator.reported_state)
    if error:
        raise AnthbotGenieApiError(error)

    serial = coordinator.client.serial_number
    presigned_url = await coordinator.account_client.async_get_firmware_presigned_url(
        serial,
        firmware.fw_url,
    )
    await coordinator.client.async_publish_service_command(
        cmd="ota_start",
        data={
            "category": "firmware",
            "version": firmware.version,
            "url": presigned_url,
            "md5": firmware.md5,
        },
    )
