# Changelog

## 2.4.9.2 — 2026-09-25

- Promotes the validated **2.4.9.2 beta line** to stable while preserving the working 2.4.9.1 base behavior and the fixes added through Beta 4.
- Adds **five browser-local map views**: **Origin, Classic, Modern, Compact and Fullscreen**. Origin preserves the familiar original layout, while the other views provide alternative responsive/map-first presentations; the selected view remains local to each browser/device.
- Keeps the responsive/mobile refinements from the beta line, including Classic portrait/landscape handling, the landscape zone/order editor, viewport-filling map layouts, and all **23 supported UI languages**.
- Fixes the Issue #64 **high-CPU hot path** without reducing telemetry cadence or changing mower commands: history metadata/URL discovery is consolidated into one traversal, and distant No-Go geometry is rejected cheaply using polygon bounding boxes before exact polygon/intersection checks.
- Preserves the working **minimal installation presence heartbeat** introduced in Beta 4, kept separate from detailed developer Reports and limited to the installation ID, integration version and mower model.
- Includes the mowing-percentage status in the information popover and retains the existing calibration, schedule, voice, map, history and model-specific behavior.

## 2.4.9.2-beta1 — 2026-09-24

- Uses **2.4.9.1 as the exact base**, preserving its Home Assistant thread-safety fix, Voice Pack Recorder protection, voice-store support and existing mower/model behavior.
- Uses the Home Assistant/AwesomeVersion-compatible prerelease string **2.4.9.2-beta1** for this Beta 1 build.
- Adds four browser-local map frontends: **Classic, Modern, Compact and Fullscreen**, without changing the shared backend command path.
- Fixes responsive sizing so the lower action bar remains reachable on laptop/tablet layouts and the Fullscreen frontend uses the available map area instead of reserving excessive empty space.
- Reworks **Classic mobile** behavior: portrait mode keeps the map visible with compact controls, while landscape mode exposes a compact **Mowing area** selector instead of relying on a long, hard-to-scroll target list.
- Adds multi-zone selection and explicit mowing order editing for Classic mobile landscape without removing the existing manual/automatic zone handling.
- Keeps the frontend selection browser/device-local and preserves the existing calibration, status/info and command functions.
- Preserves all **23 supported UI languages** and adds localized text for the new Classic mobile area/zone-order controls in every supported language.
- Adds regression coverage for the mirrored frontend bundle and the 23-language Classic mobile controls.
- Updates source-level regression checks for generated frontend markup and prerelease manifest versioning without weakening the underlying behavior checks.

## 2.4.9.1 — 2026-09-21

- Fixes Home Assistant thread-safety error #61 in the `Next mow` timestamp sensor: its one-minute refresh now runs as an event-loop callback instead of calling `async_write_ha_state()` from an executor thread.
- Keeps the existing one-minute `Next mow` refresh behavior, so time-dependent schedule state continues to update without waiting for new mower data.
- Prevents Recorder warnings for the Voice Pack select exceeding Home Assistant's 16 KiB state-attribute limit by keeping its large live catalogue/store/install diagnostics out of Recorder history while leaving them available to the current-state UI.
- Adds regression coverage for both the event-loop-safe `Next mow` refresh and the Voice Pack Recorder exclusion.

## 2.4.9.0 — 2026-09-21

- Adds **voice-pack management for speech-capable ANTHBOT Genie models**. M9/M9 Pro do not support spoken voice packs and therefore do not expose voice-pack selection or installation; their existing volume control remains available.
- Adds the **ANTHBOT Community Voice Store** flow, including free/paid catalogue entries, anonymous client pairing, Stripe-backed entitlement recognition, locked/unlocked states, and automatic entitlement refresh after returning from checkout.
- Uses the project-controlled `anthbotmap.com` endpoints for the voice catalogue, store pairing/entitlements, telemetry, diagnostics and read-only Developer Agent traffic.
- Adds verified custom/community voice installation through the ANTHBOT `voice_set` OTA path, with request state, progress, retry handling and mower-side confirmation metadata.
- Adds a built-in verified Hungarian community voice fallback and preserves model/capability guards so unsupported mowers are not offered spoken voice packages.
- Adds native Home Assistant **firmware Update entities** backed by ANTHBOT's vendor firmware metadata, presigned package URL flow, MD5 validation, manual install command, progress and release notes.
- Keeps unverified automatic firmware-update writes disabled; the robot-reported automatic-update flag remains read-only.
- Hardware validation: Community Voice Store purchase, entitlement unlock and purchased voice installation were verified end-to-end on a real **Genie 1000**. Existing mower functions were regression-checked on the OTA test build, and firmware metadata correctly reports an up-to-date mower when no newer vendor package is offered.
- Adds dedicated regression coverage for firmware OTA, model-aware voice support, paid voice-store entitlements, install verification and frontend refresh behavior.

## 2.4.8.2 — 2026-09-18

- Adds an isolated **Pion / MGC** model family and recognizes cloud model identifiers such as `MGC500`, `MGC750` and `MGC1000` instead of routing them through Genie-only behavior.
- Normalizes the confirmed flat MGC shadow fields without changing their raw vendor values, including cutting height, mowing progress/area, mowing direction, rain status, RSSI/IP, map revision, current path payload, breakpoint and board firmware data.
- Fixes Pion/MGC native weekly schedules where `week: 1..7` is a single weekday rather than a Genie-style bitmask.
- Preserves the MGC app schedule shape: one native appointment per weekday, full-lawn work mode, top-level cutting height fallback and the existing full `value` envelope instead of assuming the M-series incremental schedule payload.
- Uses the native Pion/MGC cloud wake/start path and avoids the Genie-only `app_state` preamble before `mow_start`.
- Exposes confirmed MGC cutting-height, mowing-progress and mapped-area values through the existing Home Assistant sensors using a Pion-only namespaced fallback.
- Keeps Genie, M5/M9/M9 Pro and N8 model guards unchanged and adds dedicated regression coverage for Pion/MGC isolation.
- Does **not** enable guessed Pion/MGC rain/cutting-height write payloads or a guessed `curpath` decoder; those remain disabled until the app/real hardware confirms their exact protocol.

## 2.4.8.1 — 2026-09-18

- Fixes native schedule write-back for M5/M9/N8/Pion-family mowers by using the app's model-specific `appointment` and `delete_appointment` payloads instead of the Genie `value` envelope.
- Generates the required next numeric appointment ID for new M-series rules.
- Keeps the already working Genie schedule payload unchanged.
- Hardware verification: creating an M9 Pro schedule from the Anthbot Map Card now makes it appear in the ANTHBOT app.
- Full validation before release: 365/365 unit tests passed, including separate M-series add/edit/delete payload regressions and Genie isolation coverage.

## 2.4.8.0 — 2026-09-18

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
- Shows disabled native app schedules in the Schedule tab without treating them as an upcoming mow.
- Matches `sensor.*_next_mow` to the active mower by serial number on multi-mower dashboards.
- Shows the next mow in blue inside the floating map status display only when a real upcoming mow exists.
- Hardware verification: the Genie 1000 native app schedule was successfully loaded and displayed in Home Assistant.
- Full validation before release: 363/363 unit tests passed, JavaScript syntax validation passed, and both bundled frontend copies are byte-identical.

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
