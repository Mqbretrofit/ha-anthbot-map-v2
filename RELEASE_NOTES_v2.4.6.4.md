# Anthbot Map v2.4.6.4

Maintenance release focused on field-proven reliability issues without changing normal mower-control behavior.

## Fixed

- Automatic diagnostics are now episode/edge triggered instead of re-sending the same persistent `no_go_path_crossing` (or other unchanged diagnostic condition) every hour.
- Existing diagnostic conditions are seeded when Home Assistant starts, so an old crossing is not replayed just because the integration was reloaded.
- Historical cloud task-event errors remain visible as history but gain explicit freshness/stale metadata and no longer independently trigger the automatic robot-error reporter after their freshness window has expired.
- AWS IoT live-shadow supervision now survives unexpected normal runtime/transport exceptions instead of allowing the background listener to die permanently.
- After repeated reconnect failures, the listener rotates temporary IoT credentials and continues bounded reconnect attempts; normal credential expiry handling remains in place.
- M-series map identity handling now keeps `map.map_id`, `area_id`, `plan_id` and the raster `map_id` embedded in `map_manager_<serial>.tar.gz` as separate protocol-layer identifiers.
- Once a serial-named M-series map-manager archive has been decoded, a different logical `map.map_id` no longer forces repeated downloads merely because it differs from the raster id.
- The legacy M-series archive probe no longer derives `map_manager_<map_id>.tar.gz` from the logical map id.

## Scope

- Genie live-shadow recovery applies to Genie models as well as the shared listener used elsewhere.
- M-series map changes are guarded to M5/M9-family model names.
- N8 model routing and command behavior are not widened or changed by the M-series map fix.
