"""Opt-in read-only developer test agent for uncommon ANTHBOT models.

The server can select only pre-installed probe identifiers from the whitelist in
this module. It cannot send Python code, URLs, MQTT commands, mower-control
commands or arbitrary API parameters. The user's ANTHBOT credentials never
leave Home Assistant.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVELOPER_AGENT_ENABLED,
    CONF_DEVELOPER_AGENT_KEY,
    CONF_DEVELOPER_INSTALLATION_ID,
    DEVELOPER_AGENT_POLL_ENDPOINT,
    DEVELOPER_AGENT_RESULT_ENDPOINT,
    DOMAIN,
)
from .firmware_diagnostics import build_firmware_diagnostics_report

_LOGGER = logging.getLogger(__name__)
_AGENT_TASKS_KEY = f"{DOMAIN}_developer_agent_tasks"
_LOCAL_DISABLED_RECHECK_SECONDS = 60
_NETWORK_RETRY_SECONDS = 300
_RESULT_CHUNK_CHARS = 24_000

_SENSITIVE_KEY_PARTS = (
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
    "username",
    "email",
    "url",
)
_URL_RE = re.compile(r"(?:https?|wss?)://\S+", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def _integration_version() -> str | None:
    try:
        payload = json.loads(Path(__file__).with_name("manifest.json").read_text("utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    value = payload.get("version") if isinstance(payload, dict) else None
    return str(value) if value is not None else None


def _entry_option(entry: ConfigEntry, key: str, default: bool = False) -> bool:
    if key in entry.options:
        return bool(entry.options.get(key))
    return bool(entry.data.get(key, default))


def _is_sensitive_key(value: object) -> bool:
    normalized = str(value).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _safe_text(value: str) -> str:
    value = _URL_RE.sub("<url>", value)
    value = _BEARER_RE.sub("Bearer <redacted>", value)
    return value if len(value) <= 16_384 else value[:16_384] + "…"


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    """Return JSON-safe probe data while dropping credential-like fields."""
    if depth >= 16:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, bytes):
        return {
            "byte_length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
            "first_bytes_hex": value[:64].hex(" "),
        }
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            if _is_sensitive_key(key):
                continue
            result[key] = _safe_value(child, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(child, depth=depth + 1) for child in value]
    return _safe_text(str(value))


def _serial_hash(coordinator: Any) -> str | None:
    serial = str(getattr(getattr(coordinator, "client", None), "serial_number", "") or "")
    return hashlib.sha256(serial.encode("utf-8")).hexdigest() if serial else None


def _state_schema_snapshot(coordinator: Any) -> dict[str, Any]:
    state = getattr(coordinator, "reported_state", None)
    if not isinstance(state, dict):
        state = {}

    # Even key names can disclose that a credential/token field exists in a
    # vendor response, so apply the same credential filter to both the key list
    # and the type map before anything leaves Home Assistant.
    safe_items = [
        (str(key), value)
        for key, value in state.items()
        if not _is_sensitive_key(key)
    ]
    keys = sorted(key for key, _value in safe_items)
    types = {key: type(value).__name__ for key, value in safe_items}

    selected_names = (
        "robot_sta",
        "mower_status",
        "robot_status_raw",
        "err_code",
        "fw_version",
        "firmware_version",
        "map_time",
        "map_tar_time",
        "area_time",
        "ridable_area_time",
        "path_time",
        "multi_maps",
        "has_map",
        "online",
        "rtk_state",
        "rtk_base_state",
        "cloud_task_event_code",
        "event_code",
        "_map_definition_error",
        "_path_definition_error",
        "_ridable_area_definition_error",
        "_live_shadow_error",
    )
    selected = {
        name: _safe_value(state[name])
        for name in selected_names
        if name in state and not _is_sensitive_key(name)
    }
    return {
        "top_level_keys": keys,
        "top_level_types": types,
        "selected_state": selected,
    }


async def _probe_state_schema(coordinator: Any) -> Any:
    return _state_schema_snapshot(coordinator)


async def _probe_firmware_diagnostics(coordinator: Any) -> Any:
    return build_firmware_diagnostics_report(
        coordinator,
        include_raw_state=False,
        include_identifiers=False,
    )


async def _probe_area_definition(coordinator: Any) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_area_definition(serial)


async def _probe_ridable_area_definition(coordinator: Any) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_ridable_area_definition(serial)


async def _probe_map_definition(coordinator: Any) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_map_definition(serial)


async def _probe_map_archive(coordinator: Any) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_map_archive(serial)


async def _probe_path_definition(coordinator: Any) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_path_definition(serial)


async def _probe_task_events(coordinator: Any) -> Any:
    state = coordinator.reported_state
    return state.get("_task_events") if isinstance(state, dict) else None


async def _probe_refresh_properties(coordinator: Any) -> Any:
    # Read-only app-style property refresh. It requests the current property set
    # and then lets the normal coordinator merge the response; it never publishes
    # a service command or changes mower settings.
    await coordinator.client.async_request_all_properties()
    await coordinator.async_request_refresh()
    return _state_schema_snapshot(coordinator)


Probe = Callable[[Any], Awaitable[Any]]
_PROBES: dict[str, Probe] = {
    "state_schema": _probe_state_schema,
    "firmware_diagnostics": _probe_firmware_diagnostics,
    "area_definition": _probe_area_definition,
    "ridable_area_definition": _probe_ridable_area_definition,
    "map_definition": _probe_map_definition,
    "map_archive": _probe_map_archive,
    "path_definition": _probe_path_definition,
    "task_events": _probe_task_events,
    "refresh_properties": _probe_refresh_properties,
}

# Public for tests/documentation. The server can request only one of these IDs;
# the client independently rejects everything else.
DEVELOPER_AGENT_ALLOWED_PROBES = frozenset(_PROBES)


async def _execute_job(
    coordinators: list[Any],
    *,
    action: str,
    target_model: str | None,
) -> dict[str, Any]:
    probe = _PROBES.get(action)
    if probe is None:
        return {
            "status": "rejected",
            "action": action,
            "error": "probe is not in the client whitelist",
        }

    target = target_model.strip().casefold() if isinstance(target_model, str) and target_model.strip() else None
    matches = [
        coordinator
        for coordinator in coordinators
        if target is None
        or str(getattr(getattr(coordinator, "device", None), "model", "") or "").strip().casefold() == target
    ]
    if not matches:
        return {
            "status": "error",
            "action": action,
            "target_model": target_model,
            "error": "no matching mower is loaded in this config entry",
            "targets": [],
        }

    results: list[dict[str, Any]] = []
    success_count = 0
    for coordinator in matches:
        model = str(getattr(getattr(coordinator, "device", None), "model", "") or "") or None
        try:
            data = await probe(coordinator)
            success_count += 1
            results.append(
                {
                    "model": model,
                    "serial_sha256": _serial_hash(coordinator),
                    "status": "ok",
                    "data": _safe_value(data),
                }
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - probe failures are the result
            results.append(
                {
                    "model": model,
                    "serial_sha256": _serial_hash(coordinator),
                    "status": "error",
                    "error_type": type(err).__name__,
                    "error": _safe_text(str(err)),
                }
            )

    return {
        "status": "ok" if success_count else "error",
        "action": action,
        "target_model": target_model,
        "integration_version": _integration_version(),
        "targets": results,
    }


async def _post_result_chunks(
    session: Any,
    *,
    installation_id: str,
    agent_key: str,
    job_id: int,
    result: dict[str, Any],
) -> bool:
    serialized = json.dumps(_safe_value(result), ensure_ascii=False, separators=(",", ":"))
    chunks = [
        serialized[index : index + _RESULT_CHUNK_CHARS]
        for index in range(0, len(serialized), _RESULT_CHUNK_CHARS)
    ] or ["{}"]

    for index, chunk in enumerate(chunks):
        payload = {
            "schema": "anthbot-developer-agent-result-v1",
            "installation_id": installation_id,
            "agent_key": agent_key,
            "job_id": job_id,
            "chunk_index": index,
            "chunk_count": len(chunks),
            "chunk": chunk,
        }
        delivered = False
        for attempt in range(3):
            try:
                async with session.post(
                    DEVELOPER_AGENT_RESULT_ENDPOINT,
                    json=payload,
                    timeout=15,
                    headers={"User-Agent": "Anthbot-Map-Developer-Agent/1"},
                ) as response:
                    delivered = 200 <= response.status < 300
                    if delivered:
                        break
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(2 + attempt * 3)
        if not delivered:
            return False
    return True


async def _poll_once(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> int:
    installation_id = entry.data.get(CONF_DEVELOPER_INSTALLATION_ID)
    agent_key = entry.data.get(CONF_DEVELOPER_AGENT_KEY)
    if not isinstance(installation_id, str) or not installation_id:
        return _NETWORK_RETRY_SECONDS
    if not isinstance(agent_key, str) or len(agent_key) < 32:
        return _NETWORK_RETRY_SECONDS

    coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id, [])
    if not isinstance(coordinators, list):
        coordinators = list(coordinators) if coordinators else []
    models = sorted(
        {
            str(coordinator.device.model).strip()
            for coordinator in coordinators
            if getattr(coordinator, "device", None) is not None
            and isinstance(getattr(coordinator.device, "model", None), str)
            and coordinator.device.model.strip()
        }
    )
    session = async_get_clientsession(hass)
    payload = {
        "schema": "anthbot-developer-agent-poll-v1",
        "installation_id": installation_id,
        "agent_key": agent_key,
        "integration_version": _integration_version(),
        "models": models,
    }

    try:
        async with session.post(
            DEVELOPER_AGENT_POLL_ENDPOINT,
            json=payload,
            timeout=15,
            headers={"User-Agent": "Anthbot-Map-Developer-Agent/1"},
        ) as response:
            if response.status < 200 or response.status >= 300:
                return _NETWORK_RETRY_SECONDS
            response_data = await response.json(content_type=None)
    except asyncio.CancelledError:
        raise
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Developer agent poll failed: %s", err)
        return _NETWORK_RETRY_SECONDS

    if not isinstance(response_data, dict):
        return _NETWORK_RETRY_SECONDS
    next_poll = response_data.get("next_poll_seconds", 120)
    try:
        next_poll_seconds = max(30, min(21_600, int(next_poll)))
    except (TypeError, ValueError):
        next_poll_seconds = 120

    # A server-side stop suppresses all probes/results. The lightweight poll is
    # retained at the server-selected interval so the developer can reactivate
    # the already user-authorized agent later without asking the user again.
    if response_data.get("server_enabled") is not True:
        return max(next_poll_seconds, 3_600)

    job = response_data.get("job")
    if not isinstance(job, dict):
        return next_poll_seconds
    try:
        job_id = int(job.get("job_id"))
    except (TypeError, ValueError):
        return next_poll_seconds
    action = job.get("action")
    if not isinstance(action, str) or action not in DEVELOPER_AGENT_ALLOWED_PROBES:
        result = {
            "status": "rejected",
            "action": str(action),
            "error": "server requested an action outside the client whitelist",
        }
    else:
        target_model = job.get("target_model")
        if not isinstance(target_model, str):
            target_model = None
        result = await _execute_job(
            coordinators,
            action=action,
            target_model=target_model,
        )

    sent = await _post_result_chunks(
        session,
        installation_id=installation_id,
        agent_key=agent_key,
        job_id=job_id,
        result=result,
    )
    return 5 if sent else _NETWORK_RETRY_SECONDS


async def _agent_loop(hass: HomeAssistant, entry: ConfigEntry) -> None:
    while True:
        try:
            if not _entry_option(entry, CONF_DEVELOPER_AGENT_ENABLED, False):
                await asyncio.sleep(_LOCAL_DISABLED_RECHECK_SECONDS)
                continue
            delay = await _poll_once(hass, entry)
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # noqa: BLE001 - never affect integration operation
            _LOGGER.debug("Developer agent loop error: %s", err)
            await asyncio.sleep(_NETWORK_RETRY_SECONDS)


async def async_register_developer_agent(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Start one non-blocking developer-agent loop per config entry."""
    tasks: dict[str, asyncio.Task[None]] = hass.data.setdefault(_AGENT_TASKS_KEY, {})
    existing = tasks.get(entry.entry_id)
    if existing is not None and not existing.done():
        return

    task = hass.async_create_task(
        _agent_loop(hass, entry),
        f"anthbot_developer_agent_{entry.entry_id}",
    )
    tasks[entry.entry_id] = task

    def _cancel() -> None:
        current = tasks.pop(entry.entry_id, None)
        if current is not None and not current.done():
            current.cancel()

    entry.async_on_unload(_cancel)
