from __future__ import annotations

import re

from app import app as fastapi_app
from developer_agent_api import (
    init_developer_agent_tables,
    router as developer_agent_router,
)

# Keep the developer-agent tables and routes isolated from the existing
# reporting API. Import-time initialization is idempotent and uses CREATE TABLE
# IF NOT EXISTS, so existing telemetry/diagnostics data is untouched.
init_developer_agent_tables()
fastapi_app.include_router(developer_agent_router)

# Only the dashboard HTML is embeddable, and only from the Home Assistant
# origins used by this deployment. Public ingest/admin API responses are not
# made frameable.
_FRAME_ANCESTORS = (
    "'self' "
    "http://192.168.8.91:8123 "
    "http://homeassistant.local:8123 "
    "https://ha.mqbretrofithungary.online"
)


class DashboardEmbeddingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not str(scope.get("path", "")).startswith(
            "/dashboard"
        ):
            await self.app(scope, receive, send)
            return

        async def send_wrapped(message):
            if message.get("type") == "http.response.start":
                headers = []
                for raw_name, raw_value in message.get("headers", []):
                    name = raw_name.decode("latin-1").lower()
                    if name == "x-frame-options":
                        # The FastAPI app deliberately denies framing by default.
                        # For the dashboard route we replace that with an explicit
                        # CSP allow-list for this Home Assistant deployment.
                        continue
                    if name == "content-security-policy":
                        continue
                    if name == "set-cookie":
                        value = raw_value.decode("latin-1")
                        value = re.sub(
                            r"(?i)samesite=strict",
                            "SameSite=None",
                            value,
                        )
                        raw_value = value.encode("latin-1")
                    headers.append((raw_name, raw_value))

                headers.append(
                    (
                        b"content-security-policy",
                        f"frame-ancestors {_FRAME_ANCESTORS}".encode("latin-1"),
                    )
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapped)


app = DashboardEmbeddingMiddleware(fastapi_app)
