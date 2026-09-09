from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Literal
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

USAGE_SCHEMA = "anthbot-map-anonymous-usage-v1"
DIAGNOSTICS_SCHEMA = "anthbot-map-diagnostics-upload-v1"
DEFAULT_DB_PATH = "/data/anthbot_reporting.sqlite3"
MAX_TELEMETRY_BYTES = 64 * 1024
MAX_DIAGNOSTICS_BYTES = 2 * 1024 * 1024
_DASHBOARD_COOKIE = "anthbot_admin_session"
_DASHBOARD_SESSION_SECONDS = 12 * 60 * 60

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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    value = dt or _utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _db_path() -> Path:
    return Path(os.environ.get("ANTHBOT_DB_PATH", DEFAULT_DB_PATH))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_db() -> None:
    with _db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS installations (
                installation_id TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_event TEXT NOT NULL,
                country TEXT,
                integration_version TEXT,
                home_assistant_version TEXT,
                device_count INTEGER NOT NULL,
                models_json TEXT NOT NULL,
                model_counts_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS telemetry_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                installation_id TEXT NOT NULL,
                event TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                UNIQUE(installation_id, event, generated_at)
            );

            CREATE INDEX IF NOT EXISTS idx_telemetry_received_at
                ON telemetry_events(received_at);

            CREATE TABLE IF NOT EXISTS diagnostics (
                report_id TEXT PRIMARY KEY,
                installation_id TEXT NOT NULL,
                trigger TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                received_at TEXT NOT NULL,
                report_sha256 TEXT NOT NULL,
                report_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_diagnostics_received_at
                ON diagnostics(received_at);
            CREATE INDEX IF NOT EXISTS idx_diagnostics_installation_id
                ON diagnostics(installation_id);
            CREATE INDEX IF NOT EXISTS idx_diagnostics_trigger
                ON diagnostics(trigger);
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _init_db()
    yield


app = FastAPI(
    title="ANTHBOT Map reporting server",
    version="1.1.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


class UsagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal[USAGE_SCHEMA] = Field(alias="schema")
    event: Literal["installation", "opt_in", "heartbeat"]
    generated_at: datetime
    installation_id: UUID
    integration_version: str | None = Field(default=None, max_length=64)
    home_assistant_version: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, max_length=128)
    device_count: int = Field(ge=0, le=100)
    models: list[str] = Field(default_factory=list, max_length=100)
    model_counts: dict[str, int] = Field(default_factory=dict)

    @field_validator("models")
    @classmethod
    def _validate_models(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            item = item.strip()
            if not item or len(item) > 128:
                raise ValueError("model names must be 1..128 characters")
            normalized.append(item)
        return normalized

    @field_validator("model_counts")
    @classmethod
    def _validate_model_counts(cls, value: dict[str, int]) -> dict[str, int]:
        if len(value) > 100:
            raise ValueError("too many model count entries")
        normalized: dict[str, int] = {}
        for key, count in value.items():
            key = key.strip()
            if not key or len(key) > 128:
                raise ValueError("model count keys must be 1..128 characters")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0 or count > 100:
                raise ValueError("invalid model count")
            normalized[key] = count
        return normalized

    @model_validator(mode="after")
    def _consistent_counts(self) -> "UsagePayload":
        if sum(self.model_counts.values()) != self.device_count:
            raise ValueError("model_counts must sum to device_count")
        if set(self.models) != set(self.model_counts):
            raise ValueError("models must match model_counts keys")
        return self


class DiagnosticsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: Literal[DIAGNOSTICS_SCHEMA] = Field(alias="schema")
    generated_at: datetime
    installation_id: UUID
    trigger: str = Field(min_length=1, max_length=128)
    report: dict[str, Any]


@app.middleware("http")
async def _limit_body_size(request: Request, call_next):
    if request.method == "POST":
        limit = (
            MAX_DIAGNOSTICS_BYTES
            if request.url.path.endswith("/diagnostics")
            else MAX_TELEMETRY_BYTES
        )
        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                if int(raw_length) > limit:
                    return _too_large_response(limit)
            except ValueError:
                pass
    response = await call_next(request)
    if request.url.path.startswith("/dashboard") or request.url.path.startswith(
        "/api/anthbot/admin/"
    ):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _too_large_response(limit: int):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={"detail": f"request body exceeds {limit} bytes"},
    )


def _contains_sensitive_key(value: Any, *, depth: int = 0) -> bool:
    if depth > 20:
        return True
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                return True
            if _contains_sensitive_key(child, depth=depth + 1):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(child, depth=depth + 1) for child in value)
    return False


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _admin_token() -> str:
    return os.environ.get("ANTHBOT_ADMIN_TOKEN", "")


def _dashboard_session_value() -> str:
    token = _admin_token()
    if not token:
        return ""
    return hmac.new(
        token.encode("utf-8"),
        b"anthbot-reporting-dashboard-session-v1",
        hashlib.sha256,
    ).hexdigest()


def _request_is_admin(request: Request, authorization: str | None = None) -> bool:
    expected = _admin_token()
    if not expected:
        return False
    if isinstance(authorization, str) and authorization.startswith("Bearer "):
        supplied = authorization[7:]
        if supplied and secrets.compare_digest(supplied, expected):
            return True
    cookie = request.cookies.get(_DASHBOARD_COOKIE, "")
    session_value = _dashboard_session_value()
    return bool(cookie and session_value and secrets.compare_digest(cookie, session_value))


def require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    if not _admin_token():
        raise HTTPException(status_code=503, detail="admin access is not configured")
    if not _request_is_admin(request, authorization):
        raise HTTPException(status_code=401, detail="invalid admin token")


def _dashboard_file(name: str) -> str:
    try:
        return Path(__file__).with_name(name).read_text(encoding="utf-8")
    except OSError as err:
        raise HTTPException(status_code=503, detail="dashboard asset unavailable") from err


def _installation_from_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        model_counts = json.loads(row["model_counts_json"])
    except (TypeError, ValueError):
        model_counts = {}
    if not isinstance(model_counts, dict):
        model_counts = {}
    return {
        "installation_id": row["installation_id"],
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "last_event": row["last_event"],
        "country": row["country"],
        "integration_version": row["integration_version"],
        "home_assistant_version": row["home_assistant_version"],
        "device_count": row["device_count"],
        "model_counts": model_counts,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"ok": True, "schema": "anthbot-reporting-server-v1"}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    if not _admin_token():
        html = _dashboard_file("dashboard_login.html").replace(
            "__ERROR__",
            '<div class="error">Admin access is not configured. Set admin_token in the Home Assistant app configuration.</div>',
        )
        return HTMLResponse(html, status_code=503)
    if _request_is_admin(request):
        return HTMLResponse(_dashboard_file("dashboard.html"))
    return HTMLResponse(_dashboard_file("dashboard_login.html").replace("__ERROR__", ""))


@app.post("/dashboard/login")
async def dashboard_login(request: Request):
    if not _admin_token():
        return HTMLResponse(
            _dashboard_file("dashboard_login.html").replace(
                "__ERROR__",
                '<div class="error">Admin access is not configured.</div>',
            ),
            status_code=503,
        )
    raw = (await request.body()).decode("utf-8", errors="replace")
    supplied = parse_qs(raw, keep_blank_values=True).get("token", [""])[0]
    if not supplied or not secrets.compare_digest(supplied, _admin_token()):
        return HTMLResponse(
            _dashboard_file("dashboard_login.html").replace(
                "__ERROR__", '<div class="error">Invalid admin token.</div>'
            ),
            status_code=401,
        )
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        _DASHBOARD_COOKIE,
        _dashboard_session_value(),
        max_age=_DASHBOARD_SESSION_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return response


@app.post("/dashboard/logout")
def dashboard_logout() -> RedirectResponse:
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.delete_cookie(_DASHBOARD_COOKIE, path="/")
    return response


@app.post("/api/anthbot/telemetry", status_code=202)
def ingest_telemetry(payload: UsagePayload) -> dict[str, Any]:
    received_at = _iso()
    installation_id = str(payload.installation_id)
    generated_at = _iso(payload.generated_at)
    models_json = _canonical_json(sorted(set(payload.models)))
    model_counts_json = _canonical_json(dict(sorted(payload.model_counts.items())))

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO installations (
                installation_id, first_seen, last_seen, last_event, country,
                integration_version, home_assistant_version, device_count,
                models_json, model_counts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(installation_id) DO UPDATE SET
                last_seen=excluded.last_seen,
                last_event=excluded.last_event,
                country=excluded.country,
                integration_version=excluded.integration_version,
                home_assistant_version=excluded.home_assistant_version,
                device_count=excluded.device_count,
                models_json=excluded.models_json,
                model_counts_json=excluded.model_counts_json
            """,
            (
                installation_id,
                received_at,
                received_at,
                payload.event,
                payload.country,
                payload.integration_version,
                payload.home_assistant_version,
                payload.device_count,
                models_json,
                model_counts_json,
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO telemetry_events (
                installation_id, event, generated_at, received_at
            ) VALUES (?, ?, ?, ?)
            """,
            (installation_id, payload.event, generated_at, received_at),
        )

    return {"accepted": True}


@app.post("/api/anthbot/diagnostics", status_code=202)
def ingest_diagnostics(payload: DiagnosticsPayload) -> dict[str, Any]:
    if _contains_sensitive_key(payload.report):
        raise HTTPException(
            status_code=422,
            detail="diagnostics report contains a credential-like field name",
        )

    report_json = _canonical_json(payload.report)
    if len(report_json.encode("utf-8")) > MAX_DIAGNOSTICS_BYTES:
        raise HTTPException(status_code=413, detail="diagnostics report is too large")

    report_sha256 = hashlib.sha256(report_json.encode("utf-8")).hexdigest()
    now = _utcnow()
    report_id = f"AB-{now:%Y%m%d}-{secrets.token_hex(4).upper()}"

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO diagnostics (
                report_id, installation_id, trigger, generated_at,
                received_at, report_sha256, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                str(payload.installation_id),
                payload.trigger,
                _iso(payload.generated_at),
                _iso(now),
                report_sha256,
                report_json,
            ),
        )

    return {"accepted": True, "report_id": report_id}


@app.get("/api/anthbot/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats() -> dict[str, Any]:
    now = _utcnow()
    since_7d = _iso(now - timedelta(days=7))
    since_30d = _iso(now - timedelta(days=30))
    since_24h = _iso(now - timedelta(hours=24))

    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM installations").fetchone()[0]
        total_devices = conn.execute(
            "SELECT COALESCE(SUM(device_count), 0) FROM installations"
        ).fetchone()[0]
        active_7d = conn.execute(
            "SELECT COUNT(*) FROM installations WHERE last_seen >= ?", (since_7d,)
        ).fetchone()[0]
        active_30d = conn.execute(
            "SELECT COUNT(*) FROM installations WHERE last_seen >= ?", (since_30d,)
        ).fetchone()[0]
        country_rows = conn.execute(
            """
            SELECT COALESCE(country, 'Unknown') AS name, COUNT(*) AS count
            FROM installations GROUP BY COALESCE(country, 'Unknown')
            ORDER BY count DESC, name ASC
            """
        ).fetchall()
        version_rows = conn.execute(
            """
            SELECT COALESCE(integration_version, 'Unknown') AS name, COUNT(*) AS count
            FROM installations GROUP BY COALESCE(integration_version, 'Unknown')
            ORDER BY count DESC, name ASC
            """
        ).fetchall()
        install_rows = conn.execute("SELECT model_counts_json FROM installations").fetchall()
        diag_24h = conn.execute(
            "SELECT COUNT(*) FROM diagnostics WHERE received_at >= ?", (since_24h,)
        ).fetchone()[0]
        diag_7d = conn.execute(
            "SELECT COUNT(*) FROM diagnostics WHERE received_at >= ?", (since_7d,)
        ).fetchone()[0]
        trigger_rows = conn.execute(
            """
            SELECT trigger AS name, COUNT(*) AS count
            FROM diagnostics WHERE received_at >= ?
            GROUP BY trigger ORDER BY count DESC, name ASC
            """,
            (since_30d,),
        ).fetchall()

    model_counts: dict[str, int] = {}
    for row in install_rows:
        try:
            counts = json.loads(row["model_counts_json"])
        except (TypeError, ValueError):
            continue
        if not isinstance(counts, dict):
            continue
        for model, count in counts.items():
            if isinstance(model, str) and isinstance(count, int):
                model_counts[model] = model_counts.get(model, 0) + count

    return {
        "generated_at": _iso(now),
        "installations": {
            "total": total,
            "active_7d": active_7d,
            "active_30d": active_30d,
        },
        "total_devices": total_devices,
        "by_country": [dict(row) for row in country_rows],
        "by_integration_version": [dict(row) for row in version_rows],
        "by_model": [
            {"name": name, "count": count}
            for name, count in sorted(
                model_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "diagnostics": {
            "last_24h": diag_24h,
            "last_7d": diag_7d,
            "by_trigger_30d": [dict(row) for row in trigger_rows],
        },
    }


@app.get("/api/anthbot/admin/installations", dependencies=[Depends(require_admin)])
def admin_installations(
    q: str | None = Query(default=None, max_length=160),
    country: str | None = Query(default=None, max_length=128),
    model: str | None = Query(default=None, max_length=128),
    version: str | None = Query(default=None, max_length=64),
    active_days: int | None = Query(default=None, ge=1, le=3650),
    sort: str = Query(default="last_seen", max_length=32),
    order: Literal["asc", "desc"] = Query(default="desc"),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT installation_id, first_seen, last_seen, last_event, country,
                   integration_version, home_assistant_version, device_count,
                   model_counts_json
            FROM installations
            """
        ).fetchall()

    items = [_installation_from_row(row) for row in rows]
    if country:
        items = [item for item in items if (item.get("country") or "Unknown") == country]
    if version:
        items = [
            item
            for item in items
            if (item.get("integration_version") or "Unknown") == version
        ]
    if model:
        items = [item for item in items if model in item.get("model_counts", {})]
    if active_days is not None:
        cutoff = _iso(_utcnow() - timedelta(days=active_days))
        items = [item for item in items if str(item.get("last_seen") or "") >= cutoff]
    if q:
        needle = q.casefold()
        filtered: list[dict[str, Any]] = []
        for item in items:
            haystack = " ".join(
                [
                    str(item.get("installation_id") or ""),
                    str(item.get("country") or ""),
                    str(item.get("integration_version") or ""),
                    str(item.get("home_assistant_version") or ""),
                    str(item.get("last_event") or ""),
                    " ".join(item.get("model_counts", {}).keys()),
                ]
            ).casefold()
            if needle in haystack:
                filtered.append(item)
        items = filtered

    allowed_sort = {
        "installation_id",
        "country",
        "device_count",
        "integration_version",
        "home_assistant_version",
        "first_seen",
        "last_seen",
        "last_event",
    }
    sort_key = sort if sort in allowed_sort else "last_seen"

    def _sort_value(item: dict[str, Any]):
        value = item.get(sort_key)
        if sort_key == "device_count":
            return int(value or 0)
        return str(value or "").casefold()

    items.sort(key=_sort_value, reverse=order == "desc")
    total_matching = len(items)
    return {"count": total_matching, "items": items[:limit]}


@app.get("/api/anthbot/admin/diagnostics", dependencies=[Depends(require_admin)])
def admin_diagnostics(
    limit: int = Query(default=50, ge=1, le=500),
    include_report: bool = Query(default=False),
) -> dict[str, Any]:
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT report_id, installation_id, trigger, generated_at,
                   received_at, report_sha256, report_json
            FROM diagnostics ORDER BY received_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "report_id": row["report_id"],
            "installation_id": row["installation_id"],
            "trigger": row["trigger"],
            "generated_at": row["generated_at"],
            "received_at": row["received_at"],
            "report_sha256": row["report_sha256"],
        }
        if include_report:
            item["report"] = json.loads(row["report_json"])
        items.append(item)
    return {"items": items}


@app.delete(
    "/api/anthbot/admin/diagnostics/{report_id}",
    dependencies=[Depends(require_admin)],
)
def delete_diagnostic(report_id: str) -> dict[str, Any]:
    with _db() as conn:
        cursor = conn.execute("DELETE FROM diagnostics WHERE report_id = ?", (report_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="report not found")
    return {"deleted": True, "report_id": report_id}


@app.delete(
    "/api/anthbot/admin/installations/{installation_id}",
    dependencies=[Depends(require_admin)],
)
def delete_installation(installation_id: UUID) -> dict[str, Any]:
    value = str(installation_id)
    with _db() as conn:
        conn.execute("DELETE FROM telemetry_events WHERE installation_id = ?", (value,))
        conn.execute("DELETE FROM diagnostics WHERE installation_id = ?", (value,))
        cursor = conn.execute("DELETE FROM installations WHERE installation_id = ?", (value,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="installation not found")
    return {"deleted": True, "installation_id": value}
