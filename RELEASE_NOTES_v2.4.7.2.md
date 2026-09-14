# Anthbot Map v2.4.7.2

Startup-regression and cloud-resilience hotfix rebuilt from the stable v2.4.7.0 release line.

## Fixes

- Restores the v2.4.7.0 startup-safe developer-agent lifecycle. The long-running developer agent remains a Home Assistant config-entry background task and no longer participates in bootstrap completion.
- Keeps integration-version lookups free of synchronous `manifest.json` reads on the Home Assistant event loop.
- Moves the anonymous usage heartbeat and automatic cloud-error diagnostic upload to config-entry background tasks as well, so optional reporting cannot delay Home Assistant startup.
- Re-applies the v2.4.7.1 ANTHBOT cloud/API resilience changes on top of the stable v2.4.7.0 codebase:
  - treats ANTHBOT JSON `code=5xx` responses as temporary cloud failures;
  - adds bounded retry/backoff for task-event history requests;
  - correctly classifies temporary IoT STS failures;
  - rate-limits repeated equivalent cloud warnings;
  - supports privacy-safe opt-in `cloud_api_error` diagnostics.

## Regression protection

- v2.4.7.2 is based directly on v2.4.7.0 rather than the diverged v2.4.7.1 branch.
- Live-map/WebSocket transport, Recorder optimizations, mower command routing, Battery Saver logic, and model-specific M-series/N8/Genie handling are retained from v2.4.7.0 and are not replaced by older code.
- Automated tests explicitly verify that the developer agent, usage heartbeat, and cloud-error reporting cannot become Home Assistant startup-tracked tasks.

## Upgrade note

Users on v2.4.7.1 should upgrade to v2.4.7.2. v2.4.7.1 could cause Home Assistant to wait for the long-running developer-agent loop during startup and eventually log a bootstrap timeout.

# ANTHBOT Map v2.4.7.2 – magyar változások

A v2.4.7.1-ben visszakerült indítási regresszió javítása, a stabil v2.4.7.0 alapra újraépítve.

- A developer agent ismét Home Assistant config-entry háttérfeladatként fut, ezért nem tarthatja fel a Home Assistant indulását.
- A verziólekérdezések nem olvassák szinkron módon a `manifest.json` fájlt a Home Assistant event loopban.
- Az anonim usage heartbeat és az automatikus cloud-hibariport is háttérfeladatként fut, így az opcionális riportolás nem kerülhet a startup várólistára.
- A v2.4.7.1 hasznos cloud/API stabilitási javításai megmaradnak: JSON `code=5xx` felismerés, kontrollált retry/backoff, IoT STS hibák helyes besorolása, warning ritkítás és privacy-safe `cloud_api_error` riport.
- A v2.4.7.0 live-map/WebSocket, Recorder, vezérlési, Battery Saver és modell-specifikus működése változatlan alapként marad meg.

A v2.4.7.1 használóinak javasolt a v2.4.7.2-re frissítés.
