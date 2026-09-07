"""Opt-in developer telemetry and diagnostics transport.

Nothing in this module sends data unless the caller has already checked the
corresponding user preference. The anonymous usage payload intentionally omits
account identifiers, mower serials, aliases, coordinates and credentials.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .const import COUNTRY_AREA_CODES

_LOGGER = logging.getLogger(__name__)
_USAGE_SCHEMA = "anthbot-map-anonymous-usage-v1"
_DIAGNOSTICS_SCHEMA = "anthbot-map-diagnostics-upload-v1"

# Never send developer reports to ANTHBOT/TMT vendor infrastructure. The
# reporting backend must be a server controlled by this integration project.
_BLOCKED_REPORTING_HOSTS = {"installer.tmt-automation.com"}


def _integration_version() -> str | None:
    """Read the bundled integration version without importing Home Assistant."""
    try:
        manifest = json.loads(
            Path(__file__).with_name("manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return None
    version = manifest.get("version") if isinstance(manifest, dict) else None
    return str(version) if version is not None else None


def country_name_from_area_code(area_code: object) -> str | None:
    """Return the configured country name from the Anthbot dial-code selector."""
    normalized = str(area_code or "").strip()
    for label, code in COUNTRY_AREA_CODES:
        if code == normalized:
            return label.split(" (+", 1)[0]
    return None


def build_anonymous_usage_payload(
    *,
    installation_id: str,
    area_code: object,
    devices: Iterable[Any],
    home_assistant_version: str | None,
    event: str = "installation",
) -> dict[str, Any]:
    """Build the minimal anonymous usage payload sent after opt-in."""
    models: list[str] = []
    for device in devices:
        model = getattr(device, "model", None)
        if isinstance(model, str) and model.strip():
            models.append(model.strip())

    model_counts = dict(sorted(Counter(models).items()))
    return {
        "schema": _USAGE_SCHEMA,
        "event": event,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "installation_id": str(installation_id),
        "integration_version": _integration_version(),
        "home_assistant_version": home_assistant_version,
        "country": country_name_from_area_code(area_code),
        "device_count": len(models),
        "models": sorted(set(models)),
        "model_counts": model_counts,
    }


def build_diagnostics_upload_payload(
    *,
    installation_id: str,
    report: dict[str, Any],
    trigger: str,
) -> dict[str, Any]:
    """Wrap one already privacy-filtered firmware report for server upload."""
    return {
        "schema": _DIAGNOSTICS_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "installation_id": str(installation_id),
        "trigger": str(trigger),
        "report": report,
    }


def reporting_endpoint_allowed(endpoint: object) -> bool:
    """Allow only HTTPS endpoints on project-controlled infrastructure."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        return False
    try:
        parsed = urlparse(endpoint.strip())
    except ValueError:
        return False
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and bool(hostname)
        and hostname not in _BLOCKED_REPORTING_HOSTS
    )


async def async_post_json(
    session: Any,
    endpoint: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: int = 8,
) -> bool:
    """POST JSON without ever making developer reporting block integration setup."""
    if not reporting_endpoint_allowed(endpoint):
        _LOGGER.debug("Developer reporting endpoint is disabled or not allowed")
        return False
    try:
        async with session.post(
            endpoint,
            json=payload,
            timeout=timeout_seconds,
            headers={"User-Agent": "Anthbot-Map-Developer-Reporting/1"},
        ) as response:
            if 200 <= response.status < 300:
                return True
            _LOGGER.debug(
                "Developer reporting endpoint returned HTTP %s for %s",
                response.status,
                endpoint,
            )
    except Exception as err:  # noqa: BLE001 - reporting must stay best-effort
        _LOGGER.debug("Developer reporting failed for %s: %s", endpoint, err)
    return False


async def async_send_anonymous_usage_report(
    session: Any,
    endpoint: str,
    *,
    installation_id: str,
    area_code: object,
    devices: Iterable[Any],
    home_assistant_version: str | None,
    event: str = "installation",
) -> bool:
    """Build and send one opt-in anonymous usage report."""
    payload = build_anonymous_usage_payload(
        installation_id=installation_id,
        area_code=area_code,
        devices=devices,
        home_assistant_version=home_assistant_version,
        event=event,
    )
    return await async_post_json(session, endpoint, payload)


async def async_send_diagnostics_report(
    session: Any,
    endpoint: str,
    *,
    installation_id: str,
    report: dict[str, Any],
    trigger: str,
) -> bool:
    """Send one opt-in privacy-filtered diagnostics report."""
    payload = build_diagnostics_upload_payload(
        installation_id=installation_id,
        report=report,
        trigger=trigger,
    )
    return await async_post_json(session, endpoint, payload)
