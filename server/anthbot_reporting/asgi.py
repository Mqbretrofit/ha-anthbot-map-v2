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

_DASHBOARD_DIAGNOSTICS_SCRIPT = """
<script>
(() => {
  const processed = new WeakSet();

  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'
  }[c]));

  const fmt = (v) => {
    if (!v) return '—';
    try {
      return new Intl.DateTimeFormat('hu-HU', {
        dateStyle: 'medium',
        timeStyle: 'short'
      }).format(new Date(v));
    } catch (_) {
      return String(v);
    }
  };

  const shortId = (v) => v ? String(v).slice(0, 8) + '…' : '—';

  const ensureStyle = () => {
    if (document.getElementById('anthbot-report-groups-style')) return;
    const style = document.createElement('style');
    style.id = 'anthbot-report-groups-style';
    style.textContent = `
      .report-groups{display:grid;gap:14px}
      .report-group{display:grid;gap:8px}
      .report-group-head{display:flex;align-items:center;justify-content:space-between;gap:10px;color:#dce7f8;font-weight:700}
      .report-group-count{color:#9fb0ca;font-size:.78rem;font-weight:500}
      .report-empty{padding:12px;border:1px dashed #263349;border-radius:11px;color:#9fb0ca;font-size:.82rem}
      .diag-item.report-robot{border-color:rgba(128,224,199,.25)}
      .diag-item.report-integration{border-color:rgba(106,169,255,.25)}
      .report-identity{display:flex;gap:6px;flex-wrap:wrap;margin-top:5px}
      .report-mini{display:inline-flex;align-items:center;padding:2px 6px;border-radius:999px;border:1px solid #263349;background:#0e1828;color:#c8d7ed;font-size:.72rem}
      .report-type-robot{color:#baf7e7;border-color:rgba(128,224,199,.28)}
      .report-type-integration{color:#cfe3ff;border-color:rgba(106,169,255,.32)}
    `;
    document.head.appendChild(style);
  };

  const openReport = (reportId) => {
    location.href = '/dashboard/diagnostics/' + encodeURIComponent(reportId);
  };

  const itemHtml = (item) => {
    const typeClass = item.report_type === 'robot'
      ? 'report-robot'
      : item.report_type === 'integration'
        ? 'report-integration'
        : '';
    const badgeClass = item.report_type === 'robot'
      ? 'report-type-robot'
      : item.report_type === 'integration'
        ? 'report-type-integration'
        : '';
    const identity = [];
    if (item.robot_model) identity.push(`<span class="report-mini">${esc(item.robot_model)}</span>`);
    if (item.robot_id) identity.push(`<span class="report-mini mono">${esc(item.robot_id)}</span>`);
    if (!item.robot_model && !item.robot_id) {
      identity.push(`<span class="report-mini">telepítés: ${esc(shortId(item.installation_id))}</span>`);
    }

    return `
      <div class="diag-item ${typeClass}" data-report-id="${esc(item.report_id)}" tabindex="0" role="link">
        <div class="diag-main">
          <div class="diag-title">${esc(item.trigger || 'diagnosztika')}</div>
          <div class="diag-meta">${esc(item.report_id)} · ${esc(fmt(item.received_at))}</div>
          <div class="report-identity">${identity.join('')}</div>
        </div>
        <span class="pill ${badgeClass}">${esc(item.report_type_label || 'Egyéb')}</span>
      </div>`;
  };

  const groupHtml = (title, items) => `
    <div class="report-group">
      <div class="report-group-head">
        <span>${esc(title)}</span>
        <span class="report-group-count">${items.length} riport</span>
      </div>
      ${items.length ? items.map(itemHtml).join('') : '<div class="report-empty">Nincs ilyen riport.</div>'}
    </div>`;

  async function renderGroupedDiagnostics(box) {
    if (!box || processed.has(box)) return;
    processed.add(box);
    ensureStyle();

    try {
      const res = await fetch('/api/anthbot/admin/diagnostics/summary?limit=50', {
        credentials: 'same-origin'
      });
      if (res.status === 401) {
        location.href = '/dashboard';
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const items = Array.isArray(data.items) ? data.items : [];
      const robot = items.filter(x => x.report_type === 'robot');
      const integration = items.filter(x => x.report_type === 'integration');
      const other = items.filter(x => !['robot','integration'].includes(x.report_type));

      box.innerHTML = `
        <div class="report-groups">
          ${groupHtml('Robot / firmware riportok', robot)}
          ${groupHtml('Integrációs riportok', integration)}
          ${other.length ? groupHtml('Egyéb riportok', other) : ''}
        </div>`;

      box.querySelectorAll('.diag-item[data-report-id]').forEach((item) => {
        const reportId = item.dataset.reportId;
        if (!reportId) return;
        item.style.cursor = 'pointer';
        item.setAttribute('aria-label', 'Diagnosztika megnyitása: ' + reportId);
        item.addEventListener('click', () => openReport(reportId));
        item.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            openReport(reportId);
          }
        });
      });
    } catch (err) {
      box.innerHTML = `<div class="empty">A riportok csoportosítása nem sikerült: ${esc(err.message)}</div>`;
    }
  }

  const wire = () => {
    const box = document.getElementById('diag-list');
    if (box) renderGroupedDiagnostics(box);
  };

  new MutationObserver(wire).observe(document.documentElement, {
    childList: true,
    subtree: true
  });
  wire();
})();
</script>
""".encode("utf-8")


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

        inject_diagnostics = path.rstrip("/") == "/dashboard"

        async def send_wrapped(message):
            if message.get("type") == "http.response.start":
                headers = []
                for raw_name, raw_value in message.get("headers", []):
                    name = raw_name.decode("latin-1").lower()
                    if name == "x-frame-options":
                        continue
                    if name == "content-security-policy":
                        continue
                    if inject_diagnostics and name == "content-length":
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

            elif message.get("type") == "http.response.body" and inject_diagnostics:
                body = message.get("body", b"")
                if b"</body>" in body:
                    body = body.replace(
                        b"</body>",
                        _DASHBOARD_DIAGNOSTICS_SCRIPT + b"</body>",
                        1,
                    )
                    message = {**message, "body": body}

            await send(message)

        await self.app(scope, receive, send_wrapped)


app = DashboardEmbeddingMiddleware(DeveloperAgentStorageMiddleware(fastapi_app))
