from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import _dashboard_file, _db, _request_is_admin, require_admin

router = APIRouter()

_INTEGRATION_TRIGGERS = {
    "path_definition_error",
    "map_definition_error",
    "ridable_area_definition_error",
    "live_shadow_error",
}


def _robot_summary(report: Any) -> dict[str, Any]:
    """Return lightweight mower identity fields already present in a stored report."""
    if not isinstance(report, dict):
        report = {}
    device = report.get("device")
    if not isinstance(device, dict):
        device = {}
    return {
        "model": device.get("model"),
        "alias": device.get("alias"),
        "serial_number": device.get("serial_number"),
        "serial_sha256": device.get("serial_sha256"),
    }


def _diagnostic_event_summary(report: Any) -> dict[str, Any] | None:
    """Return the privacy-filtered automatic mower-error context, when present."""
    if not isinstance(report, dict):
        return None
    event = report.get("diagnostic_event")
    if not isinstance(event, dict):
        return None

    task_event = event.get("task_event")
    if not isinstance(task_event, dict):
        task_event = {}

    summary = {
        "trigger": event.get("trigger"),
        "err_code": event.get("err_code"),
        "err_description": event.get("err_description"),
        "event_code": event.get("event_code"),
        "cloud_task_event_code": event.get("cloud_task_event_code"),
        "mode": event.get("mode"),
        "robot_sta": event.get("robot_sta"),
        "online": event.get("online"),
        "task_event_code": task_event.get("code"),
        "task_event_type": task_event.get("code_type"),
        "task_event_message": (
            task_event.get("message")
            or task_event.get("msg")
            or task_event.get("content")
            or task_event.get("description")
        ),
    }
    if not any(value is not None and value != "" for value in summary.values()):
        return None
    return summary


def _report_kind(report: Any, trigger: object) -> str:
    """Return manufacturer/integration category, including legacy reports."""
    if isinstance(report, dict):
        value = report.get("report_kind")
        if value in {"manufacturer", "integration"}:
            return str(value)
        schema = str(report.get("schema") or "")
        if "integration-diagnostics" in schema:
            return "integration"
    return "integration" if str(trigger) in _INTEGRATION_TRIGGERS else "manufacturer"


@router.get(
    "/api/anthbot/admin/diagnostics-summary",
    dependencies=[Depends(require_admin)],
)
def admin_diagnostics_summary(
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    """Return lightweight diagnostic rows including mower and report category."""
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
        try:
            report = json.loads(row["report_json"])
        except (TypeError, ValueError):
            report = {}
        items.append(
            {
                "report_id": row["report_id"],
                "installation_id": row["installation_id"],
                "trigger": row["trigger"],
                "generated_at": row["generated_at"],
                "received_at": row["received_at"],
                "report_sha256": row["report_sha256"],
                "report_kind": _report_kind(report, row["trigger"]),
                "robot": _robot_summary(report),
                "diagnostic_event": _diagnostic_event_summary(report),
            }
        )
    return {"items": items}


@router.get(
    "/api/anthbot/admin/diagnostics/{report_id}",
    dependencies=[Depends(require_admin)],
)
def admin_diagnostic_detail(report_id: str) -> dict[str, Any]:
    """Return one complete stored diagnostic report for the admin dashboard."""
    with _db() as conn:
        row = conn.execute(
            """
            SELECT report_id, installation_id, trigger, generated_at,
                   received_at, report_sha256, report_json
            FROM diagnostics WHERE report_id = ?
            """,
            (report_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="report not found")

    try:
        report = json.loads(row["report_json"])
    except (TypeError, ValueError) as err:
        raise HTTPException(status_code=500, detail="stored report is invalid") from err

    return {
        "report_id": row["report_id"],
        "installation_id": row["installation_id"],
        "trigger": row["trigger"],
        "generated_at": row["generated_at"],
        "received_at": row["received_at"],
        "report_sha256": row["report_sha256"],
        "report_kind": _report_kind(report, row["trigger"]),
        "report": report,
    }


@router.get("/dashboard/diagnostics/{report_id}", response_class=HTMLResponse)
def dashboard_diagnostic_detail(report_id: str, request: Request):
    """Serve the human-readable detail page for one diagnostic report."""
    if not _request_is_admin(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return HTMLResponse(_dashboard_file("diagnostic_detail.html"))
