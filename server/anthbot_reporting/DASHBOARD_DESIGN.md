# Reporting dashboard scope

The admin dashboard is an additive reporting-server feature. It must not change ANTHBOT mower control, map/path assembly, battery-saver behavior, telemetry consent defaults, or public ingest schemas.

Dashboard features:

- admin-token login with Secure/HttpOnly/SameSite=Strict session cookie;
- total installs, active installs, mower count, diagnostics counters;
- country, mower model and integration-version distributions;
- installation table with country/model/version/activity filtering and sorting;
- latest diagnostics list;
- existing Bearer-token admin API remains supported.

The dashboard is served by the reporting app only and is independent of the Home Assistant integration runtime.
