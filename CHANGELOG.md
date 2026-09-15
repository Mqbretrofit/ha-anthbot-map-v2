# Changelog

## 2.4.7.4 — 2026-09-15

- Fixes the live-map robot orientation regression where horizontal direction could be mirrored while vertical direction remained correct.
- Keeps `yaw` and `heading` as separate telemetry representations instead of relabelling `heading` as `yaw`.
- Prefers the previously hardware-verified cloud/app `pose.yaw` when available, while retaining `heading` as a fallback.
- Preserves the existing global heading conversion, so the earlier M9 Pro direction fix is not reverted.
- Adds regression coverage for conflicting yaw/heading telemetry and keeps the bundled frontend copies byte-identical.
- Validation passed before release: unit tests, HACS validation, Hassfest, JavaScript syntax checks, and frontend mirror checks.

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
