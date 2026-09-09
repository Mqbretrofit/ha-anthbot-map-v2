"""Privacy-aware ANTHBOT firmware diagnostics report generation.

The report is designed for sharing reproducible mower/firmware problems with
ANTHBOT engineering. It intentionally excludes account credentials and cloud
secrets. Raw coordinator state is omitted by default and can only be added by
an explicit caller opt-in.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, urlparse

from .path_zone_check import no_go_zones

_SCHEMA = "anthbot-firmware-diagnostics-v1"
_MAX_DEPTH = 12
_MAX_STRING = 8192
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
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
)


def _integration_version() -> str | None:
    """Read the bundled manifest version without importing Home Assistant."""
    try:
        payload = json.loads(Path(__file__).with_name("manifest.json").read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    version = payload.get("version") if isinstance(payload, dict) else None
    return str(version) if version is not None else None


def _unwrap_value(value: Any) -> Any:
    """Unwrap simple ANTHBOT value envelopes without following cycles."""
    seen: set[int] = set()
    while isinstance(value, dict) and set(value).issubset({"value", "time", "timestamp"}) and "value" in value:
        identity = id(value)
        if identity in seen:
            return None
        seen.add(identity)
        value = value.get("value")
    return value


def _safe_get(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    """Return JSON-safe data while redacting credential-like keys."""
    if depth >= _MAX_DEPTH:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value if len(value) <= _MAX_STRING else value[:_MAX_STRING] + "…"
    if isinstance(value, bytes):
        return {"byte_length": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(key):
                result[str(key)] = "<redacted>"
            else:
                result[str(key)] = _json_safe(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, depth=depth + 1) for item in value]
    return str(value)


def _url_metadata(value: Any) -> Any:
    """Preserve useful URL metadata without leaking signed query values."""
    if not isinstance(value, str) or not value.strip():
        return _json_safe(value)
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return "<url-redacted>"
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return "<url-redacted>"
    filename = Path(parsed.path).name or None
    try:
        query_keys = sorted({key for key, _item in parse_qsl(parsed.query, keep_blank_values=True)})
    except ValueError:
        query_keys = []
    return {
        "redacted": True,
        "scheme": parsed.scheme.lower(),
        "host": parsed.hostname.lower(),
        "filename": filename,
        "query_keys": query_keys,
    }


def _diagnostic_safe(value: Any, *, depth: int = 0) -> Any:
    """Return diagnostic metadata while replacing URL values with safe summaries."""
    if depth >= _MAX_DEPTH:
        return "<max-depth>"
    if isinstance(value, str):
        if value.strip().lower().startswith(("http://", "https://")):
            return _url_metadata(value)
        return _json_safe(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.lower().replace("-", "_")
            if _is_sensitive_key(key):
                result[key] = "<redacted>"
            elif "url" in normalized or normalized.endswith("uri"):
                result[key] = _url_metadata(item)
            else:
                result[key] = _diagnostic_safe(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_diagnostic_safe(item, depth=depth + 1) for item in value]
    return _json_safe(value, depth=depth)


def _safe_error_text(value: Any) -> str | None:
    """Keep the actual exception text while stripping any embedded signed URLs."""
    if value is None:
        return None
    text = str(value)
    text = _URL_RE.sub("<url-redacted>", text)
    return text if len(text) <= _MAX_STRING else text[:_MAX_STRING] + "…"


def _definition_metadata(value: Any) -> dict[str, Any]:
    """Summarize one cached definition without duplicating its full geometry."""
    if value is None:
        return {"present": False, "type": None}
    result: dict[str, Any] = {
        "present": bool(value),
        "type": type(value).__name__,
    }
    if isinstance(value, list):
        result["item_count"] = len(value)
        return result
    if not isinstance(value, dict):
        return result

    result["top_level_keys"] = sorted(
        str(key) for key in value if not _is_sensitive_key(key)
    )
    for key in (
        "map_id",
        "path_id",
        "md5",
        "filename",
        "file_name",
        "size",
        "byte_length",
        "version",
        "time",
        "timestamp",
        "_m_series_first_index",
        "_m_series_last_index",
    ):
        if key in value:
            result[key] = _diagnostic_safe(value[key])
    if "_download_source" in value:
        result["download_source"] = _diagnostic_safe(value["_download_source"])
    return result


def _path_points(state: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    definition = state.get("_path_definition")
    if isinstance(definition, dict):
        points = definition.get("_path_points")
        if isinstance(points, list):
            return points, definition
    for key in ("path", "mowed_path", "cloud_path", "trajectory"):
        points = state.get(key)
        if isinstance(points, list):
            return points, {}
    return [], definition if isinstance(definition, dict) else {}


def _state_subset(state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "robot_sta",
        "mower_status",
        "robot_status_raw",
        "mode",
        "elec",
        "err_code",
        "rtk_state",
        "rtk_base_state",
        "ctl_rtk_base",
        "pose",
        "cur_pose",
        "gps_latitude",
        "gps_longitude",
        "mowing_area_new",
        "mowing_time_new",
        "mowing_progress",
        "progress_percent",
        "event_code",
        "cloud_task_event_code",
        "rain_continue_time",
        "online",
        "timestamp",
        "map_time",
        "map_tar_time",
        "path_time",
        "fw_version",
    )
    return {key: _json_safe(state[key]) for key in keys if key in state}


def _latest_task_event(state: dict[str, Any]) -> dict[str, Any] | None:
    payload = state.get("_task_events")
    if isinstance(payload, dict):
        items = payload.get("data")
    else:
        items = payload
    if not isinstance(items, list):
        return None
    candidates = [item for item in items if isinstance(item, dict)]
    if not candidates:
        return None

    def event_sort_key(item: dict[str, Any]) -> tuple[int, str]:
        raw = item.get("create_time", item.get("time", item.get("timestamp")))
        try:
            return (1, str(int(raw)))
        except (TypeError, ValueError):
            return (0, str(raw or ""))

    return max(candidates, key=event_sort_key)


def _serial_hash(serial_number: str) -> str:
    return hashlib.sha256(serial_number.encode("utf-8")).hexdigest()


def build_firmware_diagnostics_report(
    coordinator: Any,
    *,
    note: str | None = None,
    include_raw_state: bool = False,
    include_identifiers: bool = True,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a shareable report from one mower coordinator."""
    state = getattr(coordinator, "reported_state", None)
    if not isinstance(state, dict):
        state = {}
    device = getattr(coordinator, "device", None)
    client = getattr(coordinator, "client", None)
    serial = str(getattr(client, "serial_number", "") or "")
    model = str(getattr(device, "model", "") or "")
    alias = str(getattr(device, "alias", "") or "")
    is_owner = getattr(device, "is_owner", None)

    points, definition = _path_points(state)
    path_id = definition.get("path_id") if isinstance(definition, dict) else None
    point_count = len(points)
    no_go_check = state.get("_no_go_path_check")
    if not isinstance(no_go_check, dict):
        no_go_check = {}

    map_definition = state.get("_map_definition")
    path_definition = state.get("_path_definition")
    map_error = state.get("_map_definition_error")
    if map_error is None:
        map_error = getattr(coordinator, "_map_definition_error", None)
    path_error = state.get("_path_definition_error")
    if path_error is None:
        path_error = getattr(coordinator, "_path_definition_error", None)
    ridable_error = state.get("_ridable_area_definition_error")
    if ridable_error is None:
        ridable_error = getattr(coordinator, "_ridable_area_definition_error", None)

    map_source = state.get("_map_definition_source")
    if map_source is None:
        map_source = getattr(coordinator, "_map_definition_source", None)
    history_source = state.get("_history_path_source")
    if history_source is None:
        history_source = getattr(coordinator, "_history_path_source", None)
    history_info = state.get("_history_path_info")
    if history_info is None:
        history_info = getattr(coordinator, "_history_path_info", None)

    firmware = _unwrap_value(_safe_get(state, "fw_version", "system_version"))
    if firmware is None:
        firmware = _unwrap_value(state.get("firmware_version"))

    when = generated_at or datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "schema": _SCHEMA,
        "generated_at": when.astimezone(timezone.utc).isoformat(),
        "purpose": "Reproducible ANTHBOT firmware/path diagnostics",
        "user_note": note.strip() if isinstance(note, str) and note.strip() else None,
        "integration": {
            "domain": "anthbot_map",
            "version": _integration_version(),
        },
        "device": {
            "model": model or None,
            "firmware_version": _json_safe(firmware),
            "is_owner": is_owner if isinstance(is_owner, bool) else None,
            "serial_sha256": _serial_hash(serial) if serial else None,
            "serial_number": serial if include_identifiers and serial else None,
            "alias": alias if include_identifiers and alias else None,
        },
        "connection": {
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "live_shadow_connected": getattr(coordinator, "_live_shadow_connected", None),
            "live_shadow_error": _safe_error_text(getattr(coordinator, "_live_shadow_error", None)),
        },
        "telemetry": _state_subset(state),
        "latest_task_event": _json_safe(_latest_task_event(state)),
        "definitions": {
            "map": {
                "error": _safe_error_text(map_error),
                "source": _json_safe(map_source),
                "map_time": _json_safe(state.get("map_time")),
                "map_tar_time": _json_safe(state.get("map_tar_time")),
                "last_map_time": _json_safe(getattr(coordinator, "_last_map_time", None)),
                "last_map_key": _json_safe(getattr(coordinator, "_last_map_key", None)),
                "archive_selection": _diagnostic_safe(state.get("_map_archive_selection")),
                "cached_definition": _definition_metadata(map_definition),
            },
            "path": {
                "error": _safe_error_text(path_error),
                "source": _json_safe(history_source),
                "path_time": _json_safe(state.get("path_time")),
                "last_path_time": _json_safe(getattr(coordinator, "_last_path_time", None)),
                "history_info": _diagnostic_safe(history_info),
                "cached_definition": _definition_metadata(path_definition),
            },
            "ridable_area": {
                "error": _safe_error_text(ridable_error),
                "ridable_area_time": _json_safe(state.get("ridable_area_time")),
            },
        },
        "path": {
            "source": history_source,
            "path_id": _json_safe(path_id),
            "point_count": point_count,
            "first_point": _json_safe(points[0]) if points else None,
            "last_point": _json_safe(points[-1]) if points else None,
            "first_index": definition.get("_m_series_first_index") if isinstance(definition, dict) else None,
            "last_index": definition.get("_m_series_last_index") if isinstance(definition, dict) else None,
            "points": _json_safe(points),
        },
        "no_go": {
            "check": _json_safe(no_go_check),
            "zones": _json_safe(no_go_zones(state)),
        },
        "runtime_performance": _json_safe(state.get("runtime_performance")),
    }
    if include_raw_state:
        report["raw_state"] = _json_safe(state)
    return report


def report_filename(report: dict[str, Any]) -> str:
    """Return a deterministic safe filename prefix plus report timestamp."""
    device = report.get("device") if isinstance(report, dict) else None
    model = device.get("model") if isinstance(device, dict) else None
    serial_hash = device.get("serial_sha256") if isinstance(device, dict) else None
    model_slug = re.sub(r"[^a-z0-9]+", "-", str(model or "anthbot").lower()).strip("-") or "anthbot"
    serial_part = str(serial_hash or "unknown")[:8]
    raw_time = str(report.get("generated_at") or "")
    timestamp = re.sub(r"[^0-9]", "", raw_time)[:14] or "report"
    return f"anthbot_firmware_diag_{model_slug}_{serial_part}_{timestamp}.json"


def write_firmware_diagnostics_report(path: Path, report: dict[str, Any]) -> None:
    """Atomically write one UTF-8 JSON diagnostics report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def report_email_summary(report: dict[str, Any]) -> str:
    """Return a concise plain-text summary suitable for an email body."""
    device = report.get("device") if isinstance(report, dict) else {}
    path = report.get("path") if isinstance(report, dict) else {}
    no_go = report.get("no_go") if isinstance(report, dict) else {}
    check = no_go.get("check") if isinstance(no_go, dict) else {}
    definitions = report.get("definitions") if isinstance(report, dict) else {}
    map_definition = definitions.get("map") if isinstance(definitions, dict) else {}
    path_definition = definitions.get("path") if isinstance(definitions, dict) else {}
    lines = [
        "ANTHBOT firmware diagnostics report",
        f"Model: {device.get('model') if isinstance(device, dict) else None}",
        f"Firmware: {device.get('firmware_version') if isinstance(device, dict) else None}",
        f"Serial: {device.get('serial_number') if isinstance(device, dict) else None}",
        f"Path ID: {path.get('path_id') if isinstance(path, dict) else None}",
        f"Path points: {path.get('point_count') if isinstance(path, dict) else 0}",
        f"No-go crossing: {check.get('crossing_detected') if isinstance(check, dict) else False}",
        f"Boundary crossings: {check.get('boundary_crossings', 0) if isinstance(check, dict) else 0}",
        f"Points inside: {check.get('points_inside', 0) if isinstance(check, dict) else 0}",
        f"Traversals: {check.get('traversals', 0) if isinstance(check, dict) else 0}",
    ]
    map_error = map_definition.get("error") if isinstance(map_definition, dict) else None
    path_error = path_definition.get("error") if isinstance(path_definition, dict) else None
    if map_error:
        lines.append(f"Map definition error: {map_error}")
    if path_error:
        lines.append(f"Path definition error: {path_error}")
    note = report.get("user_note") if isinstance(report, dict) else None
    if note:
        lines.extend(("", "User note:", str(note)))
    lines.extend(("", "The attached JSON intentionally excludes account passwords, auth tokens and cloud credentials."))
    return "\n".join(lines)
