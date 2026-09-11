# v2.4.6.4 fix scope

This maintenance branch intentionally limits behavior changes to the four field-proven issues captured on 2026-09-11:

1. stale historical task-event errors being presented without freshness context;
2. repeated automatic diagnostic uploads for one unchanged condition;
3. AWS IoT live-shadow reconnects that could remain dead after transport/runtime failure;
4. M-series logical map identifiers being compared to the embedded raster map id.

No mower-control command payloads are changed. N8 routing remains isolated. The M-series map fix keeps the verified serial-named `map_manager_<serial>.tar.gz` path and does not derive map-manager filenames from logical map ids.
