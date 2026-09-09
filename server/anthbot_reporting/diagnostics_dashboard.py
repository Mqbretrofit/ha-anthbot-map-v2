from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app import _dashboard_file, _db, _request_is_admin, require_admin

router = APIRouter()


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
        "report": report,
    }


@router.get("/dashboard/diagnostics/{report_id}", response_class=HTMLResponse)
def dashboard_diagnostic_detail(report_id: str, request: Request):
    """Serve the human-readable detail page for one diagnostic report."""
    if not _request_is_admin(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return HTMLResponse(_dashboard_file("diagnostic_detail.html"))
