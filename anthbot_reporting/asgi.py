from __future__ import annotations

import re

from app import app as fastapi_app
from developer_agent_api import (
    init_developer_agent_tables,
    router as developer_agent_router,
)
from developer_agent_dashboard import router as developer_agent_dashboard_router
from diagnostics_dashboard import router as diagnostics_dashboard_router

# Keep the developer-agent routes isolated from the existing reporting API.
# Its SQLite tables are initialized lazily on the first developer-agent request
# instead of at module import time, so importing the ASGI app never requires
# write access to /data (important for tests and tooling).
fastapi_app.include_router(developer_agent_router)
fastapi_app.include_router(developer_agent_dashboard_router)
fastapi_app.include_router(diagnostics_dashboard_router)

# Only the dashboard HTML is embeddable, and only from the Home Assistant
# origins used by this deployment. Public ingest/admin API responses are not
# made frameable.
_FRAME_ANCESTORS = (
    "'self' "
    "http://192.168.8.91:8123 "
    "http://homeassistant.local:8123 "
    "https://ha.mqbretrofithungary.online"
)

_DASHBOARD_DIAGNOSTICS_LINK_SCRIPT = b"""
<style>
.diag-robot,
.diag-error,
.diag-event {
  font-size: .82rem;
  margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.diag-robot { color: #dce7f8; }
.diag-robot strong { color: #baf7e7; font-weight: 650; }
.diag-error { color: #ffd7dc; }
.diag-error strong { color: #ff9ca8; font-weight: 700; }
.diag-event { color: #ffe3a7; }
.diag-event strong { color: #ffcc66; font-weight: 650; }
</style>
<script>
(() => {
  const summaries = new Map();
  const html = (value) => String(value ?? '').replace(/[&<>\"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#039;'}[c]));

  const reportIdFor = (item) => {
    const meta = item.querySelector('.diag-meta');
    return (meta?.textContent || '').split('\\u00b7')[0].trim();
  };

  const upsertLine = (item, className, afterClassName, markup) => {
    let line = item.querySelector('.' + className);
    if (!line) {
      line = document.createElement('div');
      line.className = className;
      const anchor = item.querySelector('.' + afterClassName);
      if (anchor) anchor.insertAdjacentElement('afterend', line);
    }
    if (line) line.innerHTML = markup;
    return line;
  };

  const decorateRobot = (item, reportId) => {
    const summary = summaries.get(reportId);
    if (!summary) return;
    const robot = summary.robot || {};
    const parts = [];
    if (robot.model) parts.push(robot.model);
    if (robot.alias) parts.push(robot.alias);
    if (robot.serial_number) {
      parts.push(robot.serial_number);
    } else if (robot.serial_sha256) {
      parts.push('ID ' + String(robot.serial_sha256).slice(0, 8) + '\\u2026');
    }
    if (!parts.length) parts.push('Ismeretlen robot');

    upsertLine(
      item,
      'diag-robot',
      'diag-title',
      '<strong>Robot:</strong> ' + parts.map(html).join(' \\u00b7 '),
    );

    const diagnosticEvent = summary.diagnostic_event || null;
    if (diagnosticEvent) {
      const errorParts = [];
      if (diagnosticEvent.err_code !== null && diagnosticEvent.err_code !== undefined && diagnosticEvent.err_code !== '') {
        errorParts.push('hibakód ' + diagnosticEvent.err_code);
      }
      if (diagnosticEvent.err_description) errorParts.push(diagnosticEvent.err_description);
      if (!errorParts.length && diagnosticEvent.task_event_code) {
        errorParts.push('task event ' + diagnosticEvent.task_event_code);
      }
      if (errorParts.length) {
        upsertLine(
          item,
          'diag-error',
          'diag-robot',
          '<strong>Hiba:</strong> ' + errorParts.map(html).join(' \\u00b7 '),
        );
      }

      const contextParts = [];
      if (diagnosticEvent.event_code !== null && diagnosticEvent.event_code !== undefined && diagnosticEvent.event_code !== '') {
        contextParts.push('event ' + diagnosticEvent.event_code);
      }
      if (diagnosticEvent.cloud_task_event_code !== null && diagnosticEvent.cloud_task_event_code !== undefined && diagnosticEvent.cloud_task_event_code !== '') {
        contextParts.push('cloud ' + diagnosticEvent.cloud_task_event_code);
      }
      if (diagnosticEvent.mode) contextParts.push('mode ' + diagnosticEvent.mode);
      if (diagnosticEvent.robot_sta) contextParts.push('state ' + diagnosticEvent.robot_sta);
      if (diagnosticEvent.task_event_message) contextParts.push(diagnosticEvent.task_event_message);
      if (contextParts.length) {
        upsertLine(
          item,
          'diag-event',
          errorParts.length ? 'diag-error' : 'diag-robot',
          '<strong>Esemény:</strong> ' + contextParts.map(html).join(' \\u00b7 '),
        );
      }
    }

    const badge = item.querySelector('.pill.warn');
    if (badge) {
      const integration = summary.report_kind === 'integration';
      const automaticError = summary.trigger === 'mower_error_code' || summary.trigger === 'task_event_error';
      badge.textContent = integration
        ? 'integr\\u00e1ci\\u00f3'
        : automaticError
          ? 'gy\\u00e1ri hibariport'
          : 'gy\\u00e1ri riport';
      badge.title = integration
        ? 'Anthbot Map integr\\u00e1ci\\u00f3s diagnosztika'
        : automaticError
          ? 'Automatikusan r\\u00f6gz\\u00edtett ANTHBOT hibadiagnosztika'
          : 'ANTHBOT gy\\u00e1rt\\u00f3nak tov\\u00e1bb\\u00edthat\\u00f3 diagnosztika';
    }
  };

  const wireDiagnostics = () => {
    document.querySelectorAll('.diag-item').forEach((item) => {
      const reportId = reportIdFor(item);
      if (!reportId) return;
      decorateRobot(item, reportId);

      if (item.dataset.diagnosticLinked === '1') return;
      const open = () => {
        location.href = '/dashboard/diagnostics/' + encodeURIComponent(reportId);
      };
      item.dataset.diagnosticLinked = '1';
      item.tabIndex = 0;
      item.setAttribute('role', 'link');
      item.setAttribute('aria-label', 'Diagnosztika megnyitasa: ' + reportId);
      item.style.cursor = 'pointer';
      item.addEventListener('click', open);
      item.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          open();
        }
      });
      const badge = item.querySelector('.pill.warn');
      if (badge) badge.style.cursor = 'pointer';
    });
  };

  const loadSummaries = async () => {
    try {
      const response = await fetch('/api/anthbot/admin/diagnostics-summary?limit=20', {
        credentials: 'same-origin',
      });
      if (!response.ok) return;
      const data = await response.json();
      (data.items || []).forEach((item) => summaries.set(item.report_id, item));
      wireDiagnostics();
    } catch (_err) {
      // The dashboard remains usable even if the lightweight identity lookup fails.
    }
  };

  new MutationObserver(wireDiagnostics).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
  wireDiagnostics();
  loadSummaries();
})();
</script>
"""


class DeveloperAgentStorageMiddleware:
    """Create developer-agent tables only when one of its routes is used."""

    def __init__(self, app):
        self.app = app
        self._initialized = False

    async def __call__(self, scope, receive, send):
        path = str(scope.get("path", ""))
        if (
            scope.get("type") == "http"
            and "developer-agent" in path
            and not self._initialized
        ):
            init_developer_agent_tables()
            self._initialized = True
        await self.app(scope, receive, send)


class DashboardEmbeddingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = str(scope.get("path", ""))
        if scope.get("type") != "http" or not path.startswith("/dashboard"):
            await self.app(scope, receive, send)
            return

        inject_diagnostic_links = path.rstrip("/") == "/dashboard"

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
                    if inject_diagnostic_links and name == "content-length":
                        # The dashboard body gets a tiny navigation script below.
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

            elif message.get("type") == "http.response.body" and inject_diagnostic_links:
                body = message.get("body", b"")
                if b"</body>" in body:
                    body = body.replace(
                        b"</body>",
                        _DASHBOARD_DIAGNOSTICS_LINK_SCRIPT + b"</body>",
                        1,
                    )
                    message = {**message, "body": body}

            await send(message)

        await self.app(scope, receive, send_wrapped)


app = DashboardEmbeddingMiddleware(DeveloperAgentStorageMiddleware(fastapi_app))
