"""Temporary local-only Genie device-log/media diagnostic probe.

The official ANTHBOT app exposes ``log_switch`` and ``log_upload`` but no Genie
camera viewer. This test helper reproduces only those observed commands, captures
short-lived property/service shadow changes, redacts credentials/location data,
and stores a JSON report under ``/config/www/anthbot-device-log-probes``.
Nothing is uploaded by this helper.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import time
from typing import Any

from ..api import AnthbotGenieApiError, AnthbotShadowApiClient
from ..const import DOMAIN
from ..coordinator import AnthbotGenieDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_SERVICE = "probe_genie_device_log_media_test"
_EVENT = "anthbot_genie_device_log_media_probe_ready"
_CAPTURE_SECONDS = 18.0
_SERVICE_LIFETIME_SECONDS = 30 * 60
_OMITTED = object()

_URL_RE = re.compile(r"(?P<base>(?:https?|wss?)://[^?\s]+)(?:\?[^\s]*)?", re.I)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
_MEDIA_RE = re.compile(
    r"(?i)(camera|image|picture|photo|video|snapshot|stream|media|log|drc|upload|"
    r"file|filename|object|bucket|s3|presign|record|\.jpe?g|\.png|\.mp4|\.h264)"
)
_SENSITIVE = (
    "password",
    "passwd",
    "token",
    "secret",
    "credential",
    "authorization",
    "cookie",
    "access_key",
    "session_key",
    "session_token",
    "bearer",
)
_LOCATION = ("latitude", "longitude", "gps_lat", "gps_lon")
_INSTALLED = False


def _is_genie(value: object) -> bool:
    """Return whether a model is from the Genie family, never M5/M9."""
    model = str(value or "").upper()
    return "GENIE" in model and "M5" not in model and "M9" not in model


def _safe_text(value: str) -> str:
    value = _URL_RE.sub(lambda match: f"{match.group('base')}?<redacted>", value)
    value = _BEARER_RE.sub("Bearer <redacted>", value)
    return value if len(value) <= 8192 else value[:8192] + "…"


def _safe(value: Any, depth: int = 0) -> Any:
    if depth >= 12:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, bytes):
        return {
            "byte_length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
            "first_bytes_hex": value[:48].hex(" "),
        }
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (raw_key, child) in enumerate(value.items()):
            if index >= 250:
                result["<truncated_keys>"] = len(value) - 250
                break
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if any(part in normalized for part in _SENSITIVE):
                result[key] = "<redacted>"
            elif any(part in normalized for part in _LOCATION):
                result[key] = "<redacted-location>"
            else:
                result[key] = _safe(child, depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        sequence = list(value)
        result = [_safe(child, depth + 1) for child in sequence[:50]]
        if len(sequence) > 50:
            result.append({"<truncated_items>": len(sequence) - 50})
        return result
    return _safe_text(str(value))


def _find_key(value: Any, wanted: str, depth: int = 0) -> Any:
    if depth >= 10:
        return None
    if isinstance(value, dict):
        if wanted in value:
            return value.get(wanted)
        for child in value.values():
            found = _find_key(child, wanted, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for child in value[:50]:
            found = _find_key(child, wanted, depth + 1)
            if found is not None:
                return found
    return None


def _as_bool(value: Any) -> bool | None:
    seen: set[int] = set()
    while isinstance(value, dict) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "enabled", "enable"}:
            return True
        if normalized in {"0", "false", "off", "disabled", "disable"}:
            return False
    return None


def _interesting(value: Any, limit: int = 200) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    def visit(node: Any, path: str, depth: int) -> None:
        if len(matches) >= limit or depth >= 12:
            return
        if isinstance(node, dict):
            for raw_key, child in node.items():
                key = str(raw_key)
                child_path = f"{path}.{key}"
                if _MEDIA_RE.search(key):
                    matches.append({"path": child_path, "value": _safe(child)})
                visit(child, child_path, depth + 1)
        elif isinstance(node, (list, tuple)):
            for index, child in enumerate(node[:50]):
                visit(child, f"{path}[{index}]", depth + 1)
        elif isinstance(node, str) and (
            _MEDIA_RE.search(node)
            or node.lower().startswith(("http://", "https://", "wss://"))
        ):
            matches.append({"path": path, "value": _safe_text(node)})

    visit(value, "$", 0)
    return matches[:limit]


async def _shadow(
    client: AnthbotShadowApiClient,
    name: str,
    errors: list[dict[str, str]],
) -> dict[str, Any] | None:
    """Read the actual Genie named shadow without changing coordinator state."""
    try:
        return await client._async_get_named_shadow_reported_state(name)
    except asyncio.CancelledError:
        raise
    except Exception as err:  # noqa: BLE001
        errors.append(
            {
                "stage": f"get_{name}_shadow",
                "error_type": type(err).__name__,
                "error": _safe_text(str(err)),
            }
        )
        return None


async def _publish_exact(
    client: AnthbotShadowApiClient,
    cmd: str,
    data: Any = _OMITTED,
) -> None:
    """Publish the exact app-style desired object over the active MQTT socket."""
    publisher = getattr(client, "_live_command_publisher", None)
    if not callable(publisher):
        raise AnthbotGenieApiError(f"MQTT is not connected; '{cmd}' was not sent")
    desired: dict[str, Any] = {"cmd": cmd}
    if data is not _OMITTED:
        desired["data"] = data
    topic = f"$aws/things/{client.serial_number}/shadow/name/service/update"
    payload = json.dumps(
        {"state": {"desired": desired}}, separators=(",", ":")
    ).encode("utf-8")
    await publisher(topic, payload)


def _log_switch(*states: Any) -> Any:
    for state in states:
        value = _find_key(state, "log_switch")
        if value is not None:
            return value
    return None


def _write(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


async def _run(coordinator: Any) -> dict[str, Any]:
    client = coordinator.client
    hass = coordinator.hass
    if not _is_genie(getattr(coordinator.device, "model", None)):
        raise AnthbotGenieApiError("Device-log/media probe is Genie-only")
    if not coordinator.live_shadow_connected:
        raise AnthbotGenieApiError("Live MQTT is not connected; use Connect cloud first")

    started_mono = time.monotonic()
    errors: list[dict[str, str]] = []
    notes: list[str] = []
    commands: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    mqtt: list[dict[str, Any]] = []
    before: Any = None
    after_enable: Any = None
    after_upload: Any = None
    after_restore: Any = None
    enabled_by_probe = False

    listener = getattr(coordinator, "_live_listener", None)
    original = getattr(listener, "_on_shadow", None)
    wrapped = listener is not None and callable(original)
    if wrapped:
        async def capture(name: str, reported: dict[str, Any]) -> None:
            mqtt.append(
                {
                    "ms": round((time.monotonic() - started_mono) * 1000),
                    "shadow": name,
                    "reported": _safe(reported),
                    "interesting": _interesting(reported),
                }
            )
            await original(name, reported)

        setattr(listener, "_on_shadow", capture)
    else:
        notes.append("MQTT callback capture unavailable; API sampling still active.")

    try:
        prop = await _shadow(client, "property", errors)
        service = await _shadow(client, "service", errors)
        samples.append({"stage": "before", "property": _safe(prop), "service": _safe(service)})
        before = _log_switch(service, prop, coordinator.reported_state)

        if _as_bool(before) is False:
            try:
                await _publish_exact(client, "log_switch")
                commands.append({"cmd": "log_switch", "data": "<omitted>"})
                await asyncio.sleep(2)
                prop = await _shadow(client, "property", errors)
                service = await _shadow(client, "service", errors)
                after_enable = _log_switch(service, prop, coordinator.reported_state)
                enabled_by_probe = _as_bool(after_enable) is True
                samples.append(
                    {
                        "stage": "after_log_switch",
                        "property": _safe(prop),
                        "service": _safe(service),
                    }
                )
            except Exception as err:  # noqa: BLE001
                errors.append({"stage": "log_switch", "error": _safe_text(str(err))})
        elif _as_bool(before) is True:
            after_enable = before
            notes.append("Device Log was already enabled; it was not toggled.")
        else:
            notes.append("Device Log state was unknown; no blind toggle was sent.")

        try:
            await _publish_exact(client, "log_upload", 0)
            commands.append({"cmd": "log_upload", "data": 0})
        except Exception as err:  # noqa: BLE001
            errors.append({"stage": "log_upload", "error": _safe_text(str(err))})

        deadline = time.monotonic() + _CAPTURE_SECONDS
        index = 0
        while time.monotonic() < deadline:
            await asyncio.sleep(min(3.0, max(0.1, deadline - time.monotonic())))
            prop = await _shadow(client, "property", errors)
            service = await _shadow(client, "service", errors)
            samples.append(
                {
                    "stage": f"capture_{index}",
                    "property": _safe(prop),
                    "service": _safe(service),
                    "interesting": _interesting({"property": prop, "service": service}),
                }
            )
            index += 1
        after_upload = _log_switch(service, prop, coordinator.reported_state)
    finally:
        try:
            if enabled_by_probe:
                prop = await _shadow(client, "property", errors)
                service = await _shadow(client, "service", errors)
                if _as_bool(_log_switch(service, prop, coordinator.reported_state)) is True:
                    try:
                        await _publish_exact(client, "log_switch")
                        commands.append(
                            {"cmd": "log_switch", "data": "<omitted>", "reason": "privacy_restore"}
                        )
                        await asyncio.sleep(1)
                        prop = await _shadow(client, "property", errors)
                        service = await _shadow(client, "service", errors)
                        after_restore = _log_switch(service, prop, coordinator.reported_state)
                        if _as_bool(after_restore) is not False:
                            notes.append("Device Log OFF was not confirmed; check the app setting.")
                    except Exception as err:  # noqa: BLE001
                        errors.append({"stage": "restore", "error": _safe_text(str(err))})
                        notes.append("Device Log restore failed; check the app setting.")
        finally:
            if wrapped and listener is not None:
                setattr(listener, "_on_shadow", original)

    finished = datetime.now(timezone.utc)
    serial = str(client.serial_number)
    suffix = re.sub(r"[^A-Za-z0-9_-]", "_", serial)[-8:] or "genie"
    filename = f"anthbot_genie_log_media_probe_{suffix}_{finished:%Y%m%d_%H%M%S}.json"
    file_path = Path(hass.config.path("www", "anthbot-device-log-probes", filename))
    report = {
        "schema": "anthbot-genie-device-log-media-probe-v1",
        "generated_at": finished.isoformat(),
        "device": {
            "serial_number": serial,
            "model": str(getattr(coordinator.device, "model", "") or ""),
        },
        "probe": {
            "duration_seconds": round(time.monotonic() - started_mono, 3),
            "log_switch_before": _safe(before),
            "log_switch_after_enable": _safe(after_enable),
            "log_switch_after_upload": _safe(after_upload),
            "log_switch_after_restore": _safe(after_restore),
            "enabled_by_probe": enabled_by_probe,
            "commands": commands,
            "notes": notes,
        },
        "api_samples": samples,
        "mqtt_updates": mqtt,
        "interesting_matches": _interesting({"api": samples, "mqtt": mqtt}),
        "errors": errors,
    }
    await hass.async_add_executor_job(_write, file_path, report)
    url = f"/local/anthbot-device-log-probes/{filename}"
    result = {"file_path": str(file_path), "url": url, "errors": len(errors)}
    hass.bus.async_fire(_EVENT, {"serial_number": serial, **result})
    _LOGGER.warning("ANTHBOT Genie device-log/media probe completed: %s", result)
    return result


def _loaded_genie(hass: Any) -> list[Any]:
    result: list[Any] = []
    loaded = hass.data.get(DOMAIN, {})
    if not isinstance(loaded, dict):
        return result
    for value in loaded.values():
        for coordinator in value if isinstance(value, list) else []:
            if _is_genie(getattr(getattr(coordinator, "device", None), "model", None)):
                result.append(coordinator)
    return result


def _ensure_service(hass: Any) -> None:
    if hass.services.has_service(DOMAIN, _SERVICE):
        return

    async def handle(call: Any) -> None:
        serial = str(call.data.get("serial_number") or "").strip()
        candidates = _loaded_genie(hass)
        if serial:
            candidates = [c for c in candidates if str(c.client.serial_number) == serial]
        if not candidates:
            raise AnthbotGenieApiError("No loaded Genie mower matches the request")
        if len(candidates) != 1:
            raise AnthbotGenieApiError("Multiple Genie mowers loaded; pass serial_number")
        result = await _run(candidates[0])
        try:
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "ANTHBOT Genie log/media probe",
                    "message": f"JSON elkészült: {result['url']}",
                    "notification_id": "anthbot_genie_log_media_probe",
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            pass

    hass.services.async_register(DOMAIN, _SERVICE, handle)

    async def expire() -> None:
        await asyncio.sleep(_SERVICE_LIFETIME_SECONDS)
        if hass.services.has_service(DOMAIN, _SERVICE):
            hass.services.async_remove(DOMAIN, _SERVICE)

    hass.async_create_background_task(expire(), "anthbot_genie_log_probe_service_expiry")


def install_genie_log_probe() -> None:
    """Register the temporary service when a Genie coordinator is constructed."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    previous_init = AnthbotGenieDataUpdateCoordinator.__init__

    def coordinator_init(self: Any, *args: Any, **kwargs: Any) -> None:
        previous_init(self, *args, **kwargs)
        if _is_genie(getattr(self.device, "model", None)):
            _ensure_service(self.hass)

    AnthbotGenieDataUpdateCoordinator.__init__ = coordinator_init
