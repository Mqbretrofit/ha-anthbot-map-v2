from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import _dashboard_file, _db, _request_is_admin, require_admin

router = APIRouter()


def _diagnostic_event_summary(report: Any) -> dict[str, Any] | None:
    """Extract the privacy-filtered automatic mower-error context, when present."""
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


def _report_identity(report: Any) -> dict[str, Any]:
    """Classify one stored report and extract admin-safe mower identity."""
    if not isinstance(report, dict):
        return {
            "report_type": "other",
            "report_type_label": "Egyéb",
            "report_schema": None,
            "robot_model": None,
            "robot_id": None,
            "robot_serial_hash": None,
        }

    schema = str(report.get("schema") or "").strip() or None
    device = report.get("device")
    if not isinstance(device, dict):
        device = {}

    model = device.get("model")
    model = str(model).strip() if isinstance(model, str) and model.strip() else None
    serial = device.get("serial_number")
    serial = str(serial).strip() if isinstance(serial, str) and serial.strip() else None
    serial_hash = device.get("serial_sha256")
    serial_hash = (
        str(serial_hash).strip()
        if isinstance(serial_hash, str) and serial_hash.strip()
        else None
    )
    robot_id = serial or (f"hash:{serial_hash[:12]}" if serial_hash else None)

    is_robot_report = (
        schema == "anthbot-firmware-diagnostics-v1"
        or bool(device)
        or isinstance(report.get("telemetry"), dict)
        or isinstance(report.get("diagnostic_event"), dict)
    )
    if is_robot_report:
        return {
            "report_type": "robot",
            "report_type_label": "Robot / firmware",
            "report_schema": schema,
            "robot_model": model,
            "robot_id": robot_id,
            "robot_serial_hash": serial_hash,
        }

    integration = report.get("integration")
    is_integration_report = (
        integration == "anthbot_map"
        or isinstance(report.get("mowers"), list)
        or schema in {
            "anthbot-map-integration-diagnostics-v1",
            "anthbot-integration-diagnostics-v1",
        }
    )
    if is_integration_report:
        return {
            "report_type": "integration",
            "report_type_label": "Integráció",
            "report_schema": schema,
            "robot_model": model,
            "robot_id": robot_id,
            "robot_serial_hash": serial_hash,
        }

    return {
        "report_type": "other",
        "report_type_label": "Egyéb",
        "report_schema": schema,
        "robot_model": model,
        "robot_id": robot_id,
        "robot_serial_hash": serial_hash,
    }


def _row_payload(row: Any, *, include_report: bool) -> dict[str, Any]:
    try:
        report = json.loads(row["report_json"])
    except (TypeError, ValueError):
        report = {}

    item = {
        "report_id": row["report_id"],
        "installation_id": row["installation_id"],
        "trigger": row["trigger"],
        "generated_at": row["generated_at"],
        "received_at": row["received_at"],
        "report_sha256": row["report_sha256"],
        **_report_identity(report),
        "diagnostic_event": _diagnostic_event_summary(report),
    }
    if include_report:
        item["report"] = report
    return item


@router.get(
    "/api/anthbot/admin/diagnostics/summary",
    dependencies=[Depends(require_admin)],
)
def admin_diagnostics_summary(
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    """Return diagnostics grouped metadata without transferring full reports."""
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT report_id, installation_id, trigger, generated_at,
                   received_at, report_sha256, report_json
            FROM diagnostics ORDER BY received_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return {"items": [_row_payload(row, include_report=False) for row in rows]}


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

    item = _row_payload(row, include_report=True)
    if not isinstance(item.get("report"), dict):
        raise HTTPException(status_code=500, detail="stored report is invalid")
    return item


@router.get("/dashboard/diagnostics/{report_id}", response_class=HTMLResponse)
def dashboard_diagnostic_detail(report_id: str, request: Request):
    """Serve the human-readable detail page for one diagnostic report."""
    if not _request_is_admin(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return HTMLResponse(_dashboard_file("diagnostic_detail.html"))
