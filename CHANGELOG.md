# Changelog

## 2.4.8.0 — unreleased

- Makes the mower's native ANTHBOT app schedule the single source of truth: the HA calendar and card mirror it, while create/edit/delete operations write back with the app's `mow_regular` command.
- Preserves firmware/model-specific appointment fields while editing, and reads M5/M9/N8/Pion `time_setting.json` as a bounded fallback when the property shadow omits `appointment`.
- Adds timed schedule overrides for **mow now**, **remain parked** and **clear override**; mowing overrides return the mower to its dock when they expire.
- Adds `sensor.<mower>_next_mow`, combining active overrides, the native app schedule and any pending weather catch-up.
- Adds a native HA event entity for mowing start/completion, mower errors, stuck states, rain hold, docking, schedule starts/skips/errors and override changes.
- Adds an optional weather start guard using current conditions and hourly forecast, plus a bounded catch-up window that retries after weather clears.
- Adds a dedicated **Schedule** tab to the Anthbot Map Card. It displays the next mow and latest mower event, manages timed mow/park overrides, and creates, edits or deletes weekly zone, height and weather rules without Developer Tools.
- Lets mower firmware start native appointments, preventing duplicate HA start commands; HA records the event and only intervenes for overrides or weather holds/catch-up.
- Keeps all mower commands routed through the existing model-aware services; Genie, M5/M9-family and N8 command implementations are not replaced.
- Geometry editing remains disabled until a model-specific, write-safe ANTHBOT cloud protocol is validated; the integration does not send guessed map writes.
- Parses Genie/AWS IoT appointment envelopes that wrap the plan in `{value, timestamp}`, a bare list, a single appointment object, JSON strings, 0-6 or 1-7 weekdays, and weekday bitmasks.
- Treats Genie's `appointment_time` correctly as the revision trigger for the app's `appointment_<serial>.json` cloud file, then mirrors the real rules from that file into the HA Schedule tab and `sensor.*_next_mow`.
- Looks at `_service_reported` as well as the property shadow and refreshes the appointment file when its revision changes.

## 2.4.7.5 — 2026-09-16

- Adds an isolated M5 LiDAR live-map preference for `Anthbot M5 LiDAR`, `MGS02Radar`, and equivalent M LiDAR model identifiers.
- Uses the mobile-app-compatible current map path first: `map_<serial>.txt` with `category=device` and `sub_category=map`.
- Keeps the existing serial-named `map_manager`, selected `multi_maps`, and legacy rescue paths unchanged as fallbacks when the live map is unavailable.
- Does not alter normal M5, M9/M9 Pro, N8, Genie command, path, heading, frontend, or map-routing behavior.
- Preserves the last valid live LiDAR map across transient cloud/download failures instead of replacing it with an older archive.
- Adds regression coverage proving non-LiDAR models bypass the new wrapper, live-map success wins, live-map failure falls through to the existing stack, and transient failures retain a valid live map.
- Validation before release: 344/344 unit tests passed, including all four new M5 LiDAR regressions; Hassfest and HACS validation passed.
- M5 LiDAR hardware verification remains pending because the test mower is remote; diagnostics now expose `m5_lidar_live_map_probe` so the live source can be confirmed after installation.

## 2.4.7.4 — 2026-09-15

- Corrects the Genie 1000 live-map robot orientation using the mapping verified on real hardware.
- Genie now mirrors only the horizontal heading axis (`-heading`): left/right are corrected while up/down remain unchanged.
- Keeps the already hardware-verified M-series/M9 Pro direct heading mapping unchanged.
- Keeps `yaw` and `heading` as separate telemetry representations and prefers real `pose.yaw` when available.
- Passes the mower model into the renderer so the heading conversion is model-specific rather than global.
- Adds regression coverage for Genie vs M-series cardinal directions and keeps the bundled frontend copies byte-identical.
- Hardware verification: Genie 1000 confirmed correct in both horizontal and vertical directions before republishing v2.4.7.4.

## 2.4.7.3 — 2026-09-14

- Improves live-map performance by coalescing bursty coordinator updates before WebSocket publication.
- Moves snapshot/delta construction work out of the Home Assistant event loop and uses immutable path frames so a growing trajectory cannot produce torn live-map updates.
- Keeps reconnect/full-snapshot continuity and the existing absolute-index live-path handling intact.
- Includes the latest Genie live-path/progress presentation hardening, M-series progress post-trim handling, stationary-position handling, and location-recorder hardening from the tested 2.4.7.2 live-map performance line.
- Preserves the v2.4.7.2 startup-safe developer-agent lifecycle and cloud/API resilience fixes.
- Updates stale regression expectations to the current control router, diagnostics attributes, and M-series `stop_all_tasks` payload without changing production command routing.
- Full validation before release: 359/359 unit tests passed, plus Python compilation and live-map targeted checks.
- Repository cleanup: version-specific `CHANGELOG_v*.md` and `RELEASE_NOTES_v*.md` files are removed. Release history is consolidated here and GitHub Releases retain the published historical notes.

## 2.4.7.2 — 2026-09-14

- Restored startup-safe background handling for the long-running developer agent, usage heartbeat, and cloud-error reporting.
- Kept integration-version lookups free of synchronous manifest reads on the Home Assistant event loop.
- Re-applied temporary ANTHBOT cloud/API resilience handling on top of the stable 2.4.7.0 codebase.
- Preserved live-map/WebSocket transport, Recorder optimizations, mower command routing, Battery Saver behavior, and model-specific Genie/M-series/N8 handling.

## 2.4.7.1 — 2026-09-14

- Added bounded retry/backoff and better classification for temporary ANTHBOT cloud `5xx` responses, including JSON-level failures returned with HTTP 200.
- Added warning coalescing and privacy-safe opt-in cloud API diagnostics.

## 2.4.7.0 — 2026-09-13

- Moved high-frequency map/path/pose delivery from Home Assistant entity attributes to a dedicated WebSocket stream.
- Added full snapshot + incremental delta transport with sequence tracking, resync, path-id reset handling, and Recorder-load reduction.
- Preserved separate Genie, M-series, and N8 command/model paths.

## 2.4.6.x — 2026-09

- Added and refined optional anonymous usage statistics, automatic diagnostics, read-only Developer Agent support, N8 model handling, Recorder optimizations, and reliability improvements.

## Older versions

Older detailed notes remain available in Git history and previously published GitHub Releases. The repository now keeps a single changelog to avoid duplicated per-version documentation files.
