# Anthbot Map v2.4.6.5

Reliability and Home Assistant Recorder hotfix release built on v2.4.6.4.

## Fixed

- Removed synchronous runtime reads of `manifest.json` from Home Assistant's event loop. Developer opt-in, developer agent/reporting and firmware diagnostics now use the bundled integration-version constant.
- Hardened automatic diagnostics deduplication. Request-specific S3/cloud fields such as `RequestId`, `HostId` and signed URLs no longer make the same persistent map/path/live error look like a new failure on every retry.
- Ensured only one automatic-diagnostics listener can be installed per coordinator and added episode-clear and hard-repeat guards.
- Added a second M5/M9/M9 Pro `iot_map.bin` decoder path: the existing vector-boundary format remains preferred, with the proven LZ4 raster decoder used as fallback.
- Added privacy-safe map-manager probe diagnostics so failed decode/download stages remain visible even if the legacy fallback later returns a different 404.
- Reduced excessive Home Assistant Recorder churn found in field data from a 14.6 GB SQLite database:
  - removed fast-changing shared mower attributes from unrelated sensor and binary-sensor entities;
  - stopped task-event age counters from changing entity attributes every update;
  - reduced progress/no-go debug state churn;
  - limited dedicated pose/GPS and device-tracker state writes to 10 seconds;
  - limited the always-ready Map entity to one Home Assistant state write every 5 seconds while the coordinator continues receiving live cloud updates at full speed;
  - removed `cloud_last_success` as a per-live-flush Map state-change source.
- New diagnostic uploads include only the last four characters of the mower serial for human identification; the full serial remains omitted from automatic uploads.

## Important database note

This release prevents/reduces **future** ANTHBOT Recorder growth. It intentionally does not delete existing Home Assistant history. A database that already grew to several GB will stay large until old ANTHBOT history is purged and SQLite is repacked by the Home Assistant user/admin.

## Scope protection

No mower command routing is changed in this release. Genie, M5/M9-family and N8 control paths remain separated; the new M-series map decoding fallback does not widen N8 command handling.
