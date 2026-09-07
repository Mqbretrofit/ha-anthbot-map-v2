from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from developer_agent_api import require_admin

router = APIRouter()


@router.get(
    "/dashboard/developer-agent",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
def developer_agent_dashboard() -> HTMLResponse:
    try:
        html = Path(__file__).with_name("developer_agent_dashboard.html").read_text(
            encoding="utf-8"
        )
    except OSError as err:
        raise HTTPException(status_code=503, detail="developer-agent dashboard unavailable") from err
    return HTMLResponse(html)
