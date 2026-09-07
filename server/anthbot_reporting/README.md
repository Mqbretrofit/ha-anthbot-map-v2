# ANTHBOT Map reporting server

Small opt-in reporting backend for the ANTHBOT Map Home Assistant integration.

Production reporting hostname:

- `https://reports.mqbretrofithungary.online`

It accepts two public ingest endpoints:

- `POST /api/anthbot/telemetry` — anonymous/pseudonymous installation statistics;
- `POST /api/anthbot/diagnostics` — privacy-filtered technical diagnostics.

It also exposes admin-only JSON endpoints protected by `ANTHBOT_ADMIN_TOKEN`.

## Privacy model

The integration options are disabled by default. The server does not require a user account and the application does not store source IP addresses. The supplied nginx example disables access logging on the public ingest routes as well.

Telemetry stores only the random integration installation ID, versions, configured country, mower model names/counts and timestamps. Diagnostics are checked again server-side and rejected if a credential-like key such as `password`, `token`, `authorization`, `cookie`, `secret` or `credential` is found anywhere in the submitted report.

## Run with Docker

```bash
cp docker-compose.example.yml docker-compose.yml
# Change ANTHBOT_ADMIN_TOKEN to a long random value.
docker compose up -d --build
```

The service listens only on `127.0.0.1:8080` in the example. Put an HTTPS reverse proxy in front of it.

Health check:

```bash
curl http://127.0.0.1:8080/health
```

After DNS/TLS/reverse-proxy setup, the public check should be:

```bash
curl https://reports.mqbretrofithungary.online/health
```

## Public request contracts

### Telemetry

```json
{
  "schema": "anthbot-map-anonymous-usage-v1",
  "event": "installation",
  "generated_at": "2026-09-07T17:00:00+00:00",
  "installation_id": "2abbd72a-7748-4d50-b93f-89994d87ebef",
  "integration_version": "2.4.5",
  "home_assistant_version": "2026.9.1",
  "country": "Hungary",
  "device_count": 2,
  "models": ["Anthbot Genie 1000", "M9 Pro"],
  "model_counts": {
    "Anthbot Genie 1000": 1,
    "M9 Pro": 1
  }
}
```

Accepted `event` values are `installation`, `opt_in`, and `heartbeat`.

A valid request returns HTTP `202`:

```json
{"accepted": true}
```

### Diagnostics

```json
{
  "schema": "anthbot-map-diagnostics-upload-v1",
  "generated_at": "2026-09-07T17:01:00+00:00",
  "installation_id": "2abbd72a-7748-4d50-b93f-89994d87ebef",
  "trigger": "mower_error_code",
  "report": {
    "schema": "anthbot-firmware-diagnostics-v1",
    "device": {"model": "M9 Pro", "serial_sha256": "..."}
  }
}
```

A valid request returns HTTP `202` and a server report ID:

```json
{
  "accepted": true,
  "report_id": "AB-20260907-A1B2C3D4"
}
```

## Admin API

Set a strong `ANTHBOT_ADMIN_TOKEN`. Admin requests use:

```text
Authorization: Bearer <token>
```

Current endpoints:

- `GET /api/anthbot/admin/stats`
- `GET /api/anthbot/admin/diagnostics?limit=50`
- `GET /api/anthbot/admin/diagnostics?limit=50&include_report=true`
- `DELETE /api/anthbot/admin/diagnostics/{report_id}`
- `DELETE /api/anthbot/admin/installations/{installation_id}`

The stats endpoint returns total installations, active 7/30 day counts, country/model/version breakdowns and recent diagnostic counts. Meaningful active-user counts require the integration to send periodic opt-in `heartbeat` events.

## Database

SQLite is used by default at `/data/anthbot_reporting.sqlite3`. The container enables WAL mode. Persist `/data` using a Docker volume or bind mount.

Override the database location with:

```text
ANTHBOT_DB_PATH=/some/path/reporting.sqlite3
```

## Reverse proxy and DNS

Create DNS for `reports.mqbretrofithungary.online` pointing at the server that runs this container. `nginx.example.conf` contains body limits, rate limiting and logging recommendations. The public API should only be exposed over HTTPS. The admin routes should additionally be restricted by firewall, VPN or an IP allowlist when possible.

The Home Assistant integration test branch is already configured for:

```text
https://reports.mqbretrofithungary.online/api/anthbot/telemetry
https://reports.mqbretrofithungary.online/api/anthbot/diagnostics
```

Until DNS, TLS and the reporting container are actually online, opt-in uploads will simply fail best-effort and will not block normal integration setup or mower operation.
