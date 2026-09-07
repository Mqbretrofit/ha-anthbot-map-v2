# ANTHBOT Reporting Server

This Home Assistant app runs the opt-in ANTHBOT Map telemetry and diagnostics backend locally on port 8080.

## Configuration

`admin_token` is optional. If set, it protects the admin JSON API using `Authorization: Bearer <token>`. Public telemetry and diagnostics ingestion do not require this token.

The SQLite database is stored persistently in the app's `/data` volume as `anthbot_reporting.sqlite3` and is included with app backups.

## Cloudflare Tunnel

For the current deployment, publish:

`reports.mqbretrofithungary.online` -> `http://192.168.8.91:8080`

After the app starts, verify:

`https://reports.mqbretrofithungary.online/health`

Expected response:

```json
{"ok":true,"schema":"anthbot-reporting-server-v1"}
```

## Endpoints

- `POST /api/anthbot/telemetry`
- `POST /api/anthbot/diagnostics`
- `GET /api/anthbot/admin/stats`
- `GET /api/anthbot/admin/diagnostics`
