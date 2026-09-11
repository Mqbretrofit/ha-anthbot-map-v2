"""Opt-in read-only developer diagnostics agent for ANTHBOT integrations.

The server can select only pre-installed read-only probe identifiers from the
whitelist in this module. It cannot send Python code, URLs, MQTT commands,
mower-control commands or arbitrary API requests. The user's ANTHBOT
credentials never leave Home Assistant.

The generic diagnostic probes intentionally expose the complete in-memory
reported state (including private/internal keys) after credential redaction,
plus a safe memory inspector that can read stored object attributes without
calling methods or properties.
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
_MAX_SAFE_DEPTH = 32
_MAX_TEXT_CHARS = 65_536
_MAX_INSPECTOR_PATHS = 64
_MAX_INSPECTOR_PATH_CHARS = 1024
_MAX_DIFF_CHANGES = 50_000

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
    "agent_key",
    "api_key",
    "private_key",
    "serial_number",
    "username",
    "email",
    "url",
)
_FRAMEWORK_LINK_KEYS = frozenset(
    {
        "hass",
        "_hass",
        "loop",
        "_loop",
        "session",
        "_session",
        "websession",
        "_websession",
        "logger",
        "_logger",
        "entry",
        "_entry",
        "config_entry",
        "_config_entry",
    }
)
_DIAGNOSTIC_ROOT_NAMES = (
    "reported_state",
    "coordinator",
    "device",
    "client",
    "account_client",
)
_URL_RE = re.compile(r"(?:https?|wss?)://\S+", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
_STATE_DIFF_BASELINES: dict[int, Any] = {}


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
    return value if len(value) <= _MAX_TEXT_CHARS else value[:_MAX_TEXT_CHARS] + "…"


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    """Return JSON-safe probe data while dropping credential-like fields."""
    if depth >= _MAX_SAFE_DEPTH:
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


def _reported_state(coordinator: Any) -> dict[str, Any]:
    state = getattr(coordinator, "reported_state", None)
    return state if isinstance(state, dict) else {}


def _state_schema_snapshot(coordinator: Any) -> dict[str, Any]:
    state = _reported_state(coordinator)

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
        "_history_path_info",
        "history_path_info",
        "_history_path_source",
        "_m_series_last_mowing_record",
        "_m_series_mowing_records_source",
        "_map_archive_selection",
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


def _diagnostic_roots(coordinator: Any) -> dict[str, Any]:
    return {
        "reported_state": _reported_state(coordinator),
        "coordinator": coordinator,
        "device": getattr(coordinator, "device", None),
        "client": getattr(coordinator, "client", None),
        "account_client": getattr(coordinator, "account_client", None),
    }


def _object_inventory(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "NoneType", "attributes": {}}
    try:
        attrs = vars(value)
    except TypeError:
        return {"type": type(value).__name__, "attributes": {}}
    result: dict[str, str] = {}
    for raw_key, child in attrs.items():
        key = str(raw_key)
        if key.startswith("__") or _is_sensitive_key(key):
            continue
        result[key] = type(child).__name__
    return {
        "type": type(value).__name__,
        "attributes": dict(sorted(result.items())),
    }


def _safe_memory_value(
    value: Any,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
) -> Any:
    """Serialize in-memory diagnostic data without invoking properties/methods."""
    if depth >= 8:
        return {"__type__": type(value).__name__, "__truncated__": "max-object-depth"}

    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return _safe_value(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            if key.startswith("__") or _is_sensitive_key(key):
                continue
            result[key] = _safe_memory_value(child, depth=depth + 1, seen=seen)
        return result
    if isinstance(value, (list, tuple, set)):
        return [
            _safe_memory_value(child, depth=depth + 1, seen=seen)
            for child in value
        ]
    if callable(value):
        return {"__type__": type(value).__name__, "__callable__": True}

    if seen is None:
        seen = set()
    object_id = id(value)
    if object_id in seen:
        return {"__type__": type(value).__name__, "__cycle__": True}

    try:
        attrs = vars(value)
    except TypeError:
        return {"__type__": type(value).__name__}

    seen.add(object_id)
    result_attrs: dict[str, Any] = {}
    for raw_key, child in attrs.items():
        key = str(raw_key)
        if key.startswith("__") or _is_sensitive_key(key):
            continue
        if key in _FRAMEWORK_LINK_KEYS:
            result_attrs[key] = {"__type__": type(child).__name__, "__omitted__": "framework-link"}
            continue
        result_attrs[key] = _safe_memory_value(child, depth=depth + 1, seen=seen)
    seen.discard(object_id)
    return {
        "__type__": type(value).__name__,
        "attributes": result_attrs,
    }


def _runtime_snapshot(coordinator: Any) -> dict[str, Any]:
    roots = _diagnostic_roots(coordinator)
    return {
        "inventories": {
            name: _object_inventory(value)
            for name, value in roots.items()
            if name != "reported_state"
        },
        "objects": {
            name: _safe_memory_value(value)
            for name, value in roots.items()
            if name != "reported_state"
        },
    }


def _parse_inspector_path(path: str) -> list[tuple[str, Any]]:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    path = path.strip()
    if len(path) > _MAX_INSPECTOR_PATH_CHARS:
        raise ValueError("path is too long")

    tokens: list[tuple[str, Any]] = []
    buffer: list[str] = []
    index = 0

    def flush_key() -> None:
        if not buffer:
            return
        key = "".join(buffer).strip()
        buffer.clear()
        if not key:
            raise ValueError("empty path segment")
        if key.startswith("__") or _is_sensitive_key(key) or key in _FRAMEWORK_LINK_KEYS:
            raise ValueError("path contains a protected field")
        tokens.append(("key", key))

    while index < len(path):
        char = path[index]
        if char == ".":
            flush_key()
            index += 1
            continue
        if char == "[":
            flush_key()
            end = path.find("]", index + 1)
            if end < 0:
                raise ValueError("unterminated index/slice")
            selector = path[index + 1 : end].strip()
            if ":" in selector:
                if selector.count(":") != 1:
                    raise ValueError("slice steps are not supported")
                start_text, end_text = selector.split(":", 1)
                try:
                    start_value = int(start_text) if start_text.strip() else None
                    end_value = int(end_text) if end_text.strip() else None
                except ValueError as err:
                    raise ValueError("slice bounds must be integers") from err
                tokens.append(("slice", slice(start_value, end_value)))
            else:
                try:
                    tokens.append(("index", int(selector)))
                except ValueError as err:
                    raise ValueError("list index must be an integer") from err
            index = end + 1
            continue
        if char == "]":
            raise ValueError("unexpected closing bracket")
        buffer.append(char)
        index += 1

    flush_key()
    if not tokens:
        raise ValueError("path has no segments")
    if len(tokens) > 64:
        raise ValueError("path has too many segments")
    return tokens


def _resolve_inspector_path(coordinator: Any, path: str) -> Any:
    tokens = _parse_inspector_path(path)
    first_kind, first_value = tokens[0]
    if first_kind != "key" or first_value not in _DIAGNOSTIC_ROOT_NAMES:
        raise ValueError(
            "path must start with one of: " + ", ".join(_DIAGNOSTIC_ROOT_NAMES)
        )

    current = _diagnostic_roots(coordinator)[first_value]
    for kind, selector in tokens[1:]:
        if kind == "key":
            key = str(selector)
            if key.startswith("__") or _is_sensitive_key(key) or key in _FRAMEWORK_LINK_KEYS:
                raise ValueError("path contains a protected field")
            if isinstance(current, dict):
                if key not in current:
                    raise KeyError(key)
                current = current[key]
                continue
            try:
                attrs = vars(current)
            except TypeError as err:
                raise TypeError(f"{type(current).__name__} has no stored attributes") from err
            if key not in attrs:
                raise KeyError(key)
            current = attrs[key]
            continue

        if kind in ("index", "slice"):
            if not isinstance(current, (list, tuple)):
                raise TypeError(f"{type(current).__name__} is not indexable as a list")
            current = current[selector]
            continue

        raise ValueError("unsupported path token")

    return current


def _json_sha256(value: Any) -> str:
    serialized = json.dumps(
        _safe_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _diff_values(
    before: Any,
    after: Any,
    *,
    path: str = "$",
    changes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if changes is None:
        changes = []
    if len(changes) >= _MAX_DIFF_CHANGES:
        return changes

    if type(before) is not type(after):
        changes.append(
            {
                "path": path,
                "kind": "type_changed",
                "before": before,
                "after": after,
            }
        )
        return changes

    if isinstance(before, dict):
        before_keys = set(before)
        after_keys = set(after)
        for key in sorted(before_keys - after_keys, key=str):
            if len(changes) >= _MAX_DIFF_CHANGES:
                break
            changes.append(
                {
                    "path": f"{path}.{key}",
                    "kind": "removed",
                    "before": before[key],
                }
            )
        for key in sorted(after_keys - before_keys, key=str):
            if len(changes) >= _MAX_DIFF_CHANGES:
                break
            changes.append(
                {
                    "path": f"{path}.{key}",
                    "kind": "added",
                    "after": after[key],
                }
            )
        for key in sorted(before_keys & after_keys, key=str):
            if len(changes) >= _MAX_DIFF_CHANGES:
                break
            _diff_values(
                before[key],
                after[key],
                path=f"{path}.{key}",
                changes=changes,
            )
        return changes

    if isinstance(before, list):
        shared = min(len(before), len(after))
        for item_index in range(shared):
            if len(changes) >= _MAX_DIFF_CHANGES:
                break
            _diff_values(
                before[item_index],
                after[item_index],
                path=f"{path}[{item_index}]",
                changes=changes,
            )
        if len(changes) < _MAX_DIFF_CHANGES and len(before) > shared:
            for item_index in range(shared, len(before)):
                if len(changes) >= _MAX_DIFF_CHANGES:
                    break
                changes.append(
                    {
                        "path": f"{path}[{item_index}]",
                        "kind": "removed",
                        "before": before[item_index],
                    }
                )
        if len(changes) < _MAX_DIFF_CHANGES and len(after) > shared:
            for item_index in range(shared, len(after)):
                if len(changes) >= _MAX_DIFF_CHANGES:
                    break
                changes.append(
                    {
                        "path": f"{path}[{item_index}]",
                        "kind": "added",
                        "after": after[item_index],
                    }
                )
        return changes

    if before != after:
        changes.append(
            {
                "path": path,
                "kind": "changed",
                "before": before,
                "after": after,
            }
        )
    return changes


async def _probe_state_schema(coordinator: Any, _params: dict[str, Any]) -> Any:
    return _state_schema_snapshot(coordinator)


async def _probe_full_state(coordinator: Any, _params: dict[str, Any]) -> Any:
    """Return the complete credential-redacted in-memory reported state."""
    return {
        "schema": "anthbot-full-state-v1",
        "reported_state": _safe_value(_reported_state(coordinator)),
    }


async def _probe_full_diagnostics(coordinator: Any, _params: dict[str, Any]) -> Any:
    """Return full state plus safe runtime object inventories/snapshots."""
    return {
        "schema": "anthbot-full-diagnostics-v1",
        "state_schema": _state_schema_snapshot(coordinator),
        "reported_state": _safe_value(_reported_state(coordinator)),
        "runtime": _runtime_snapshot(coordinator),
    }


async def _probe_state_inspector(coordinator: Any, params: dict[str, Any]) -> Any:
    """Read selected stored state/object paths without calling code or properties."""
    raw_paths = params.get("paths")
    if raw_paths is None:
        raw_paths = ["reported_state"]
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]
    if not isinstance(raw_paths, list):
        raise ValueError("params.paths must be a string or list of strings")
    if len(raw_paths) > _MAX_INSPECTOR_PATHS:
        raise ValueError(f"params.paths may contain at most {_MAX_INSPECTOR_PATHS} paths")

    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for raw_path in raw_paths:
        if not isinstance(raw_path, str):
            errors[str(raw_path)] = "path must be a string"
            continue
        try:
            resolved = _resolve_inspector_path(coordinator, raw_path)
            results[raw_path] = _safe_memory_value(resolved)
        except Exception as err:  # noqa: BLE001 - path error is diagnostic output
            errors[raw_path] = f"{type(err).__name__}: {_safe_text(str(err))}"

    return {
        "schema": "anthbot-state-inspector-v1",
        "available_roots": list(_DIAGNOSTIC_ROOT_NAMES),
        "results": results,
        "errors": errors,
    }


async def _probe_state_diff(coordinator: Any, params: dict[str, Any]) -> Any:
    """Compare the current safe state with the previous state-diff snapshot."""
    current = _safe_value(_reported_state(coordinator))
    key = id(coordinator)
    previous = _STATE_DIFF_BASELINES.get(key)
    reset = bool(params.get("reset"))

    if reset or previous is None:
        _STATE_DIFF_BASELINES[key] = current
        return {
            "schema": "anthbot-state-diff-v1",
            "baseline_created": True,
            "reset": reset,
            "current_sha256": _json_sha256(current),
            "change_count": 0,
            "changes": [],
        }

    changes = _diff_values(previous, current)
    _STATE_DIFF_BASELINES[key] = current
    return {
        "schema": "anthbot-state-diff-v1",
        "baseline_created": False,
        "before_sha256": _json_sha256(previous),
        "after_sha256": _json_sha256(current),
        "change_count": len(changes),
        "truncated": len(changes) >= _MAX_DIFF_CHANGES,
        "changes": changes,
    }


async def _probe_firmware_diagnostics(coordinator: Any, _params: dict[str, Any]) -> Any:
    return build_firmware_diagnostics_report(
        coordinator,
        include_raw_state=False,
        include_identifiers=False,
    )


async def _probe_area_definition(coordinator: Any, _params: dict[str, Any]) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_area_definition(serial)


async def _probe_ridable_area_definition(coordinator: Any, _params: dict[str, Any]) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_ridable_area_definition(serial)


async def _probe_map_definition(coordinator: Any, _params: dict[str, Any]) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_map_definition(serial)


async def _probe_map_archive(coordinator: Any, _params: dict[str, Any]) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_map_archive(serial)


async def _probe_path_definition(coordinator: Any, _params: dict[str, Any]) -> Any:
    serial = coordinator.client.serial_number
    return await coordinator.account_client.async_get_device_path_definition(serial)


async def _probe_task_events(coordinator: Any, _params: dict[str, Any]) -> Any:
    state = _reported_state(coordinator)
    return state.get("_task_events")


async def _probe_refresh_properties(coordinator: Any, _params: dict[str, Any]) -> Any:
    # Read-only app-style property refresh. It requests the current property set
    # and then lets the normal coordinator merge the response; it never publishes
    # a service command or changes mower settings.
    await coordinator.client.async_request_all_properties()
    await coordinator.async_request_refresh()
    return _state_schema_snapshot(coordinator)


async def _probe_refresh_diagnostics(coordinator: Any, _params: dict[str, Any]) -> Any:
    """Refresh all read-only properties and then return the full diagnostic view."""
    await coordinator.client.async_request_all_properties()
    await coordinator.async_request_refresh()
    return {
        "schema": "anthbot-full-diagnostics-v1",
        "state_schema": _state_schema_snapshot(coordinator),
        "reported_state": _safe_value(_reported_state(coordinator)),
        "runtime": _runtime_snapshot(coordinator),
    }


Probe = Callable[[Any, dict[str, Any]], Awaitable[Any]]
_PROBES: dict[str, Probe] = {
    "state_schema": _probe_state_schema,
    "full_state": _probe_full_state,
    "full_diagnostics": _probe_full_diagnostics,
    "state_inspector": _probe_state_inspector,
    "state_diff": _probe_state_diff,
    "firmware_diagnostics": _probe_firmware_diagnostics,
    "area_definition": _probe_area_definition,
    "ridable_area_definition": _probe_ridable_area_definition,
    "map_definition": _probe_map_definition,
    "map_archive": _probe_map_archive,
    "path_definition": _probe_path_definition,
    "task_events": _probe_task_events,
    "refresh_properties": _probe_refresh_properties,
    "refresh_diagnostics": _probe_refresh_diagnostics,
}

# Public for tests/documentation. The server can request only one of these IDs;
# the client independently rejects everything else. Generic state inspection is
# performed only inside the safe diagnostic roots above and never executes code.
DEVELOPER_AGENT_ALLOWED_PROBES = frozenset(_PROBES)


async def _execute_job(
    coordinators: list[Any],
    *,
    action: str,
    target_model: str | None,
    params: dict[str, Any] | None = None,
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

    safe_params = params if isinstance(params, dict) else {}
    results: list[dict[str, Any]] = []
    success_count = 0
    for coordinator in matches:
        model = str(getattr(getattr(coordinator, "device", None), "model", "") or "") or None
        try:
            data = await probe(coordinator, safe_params)
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
        "capabilities": {
            "probe_actions": sorted(DEVELOPER_AGENT_ALLOWED_PROBES),
            "job_params": True,
            "state_inspector_paths": True,
            "full_state": True,
            "state_diff": True,
        },
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
        job_params = job.get("params")
        if not isinstance(job_params, dict):
            job_params = {}
        result = await _execute_job(
            coordinators,
            action=action,
            target_model=target_model,
            params=job_params,
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
