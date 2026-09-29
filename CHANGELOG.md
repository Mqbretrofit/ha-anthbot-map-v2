# Changelog

## 2.4.9.5-beta8 — 2026-09-29

- Uses the actual anthbotmap.com ANTHBOT MAP logo in the announcement popup.
- Reworks the popup into a smaller, calmer dark-green notification with more compact typography and actions.
- Restarts announcement polling whenever Home Assistant reattaches an existing card and refreshes immediately when the browser tab becomes visible or focused, so new popups no longer require a browser refresh.

## 2.4.9.5-beta7 — 2026-09-29

- Fixes read and popup acknowledgements being permanently tied to a reusable announcement ID.
- Treats an edited or republished message as new when its delivered content, priority or popup setting changes, so its bell and one-time popup can appear again.
- Migrates the old ID-only acknowledgement state once, making the currently published test message unread and popup-eligible again without changing Reporting Server 1.0.39.

## 2.4.9.5-beta6 — 2026-09-29

- Fixes announcement popups being swallowed by a hidden or clipped Anthbot Map card instance by rendering one branded overlay at document level.
- Prevents merely rendering a previously open News panel from silently marking a new message as read and hiding its bell.
- Marks messages as read only after the user explicitly opens News or closes the popup; the red/orange flashing bell therefore remains visible until a real read action.

## 2.4.9.5-beta5 — 2026-09-29

- Fixes the missing announcement backend registration that made the beta4 card silently hide both the notification bell and the branded automatic popup.
- Keeps the beta4 live polling, one-time popup behavior, red/orange flashing bell, personal/install/model targeting and all stable 2.4.9.4 mower controls unchanged.

## 2.4.9.5-beta4 — 2026-09-29

- Automatically checks for new announcements in the background, so popup-enabled messages appear without manually opening the News panel or pressing Refresh.
- Replaces the plain announcement dialog with an ANTHBOT Map branded dark-gradient popup using the bundled logo and priority styling.
- Adds a flashing bell beside the Information button while unread messages exist: red for important or critical messages and orange for normal messages.
- Keeps the bell visible until the message is read or its popup is closed, and opens the News panel directly when the bell is pressed.
- Preserves beta3 personal/per-installation targeting and the stable 2.4.9.4 mower-control path.

## 2.4.9.5-beta3 — 2026-09-29

- Adds the **Personal message** announcement category and localized labels in all 23 supported card languages.
- Works with Reporting Server 1.0.38, whose message editor adds the personal-message type and an **Összes kijelölése** action for all currently available target models.
- Preserves beta2 per-installation targeting and the stable 2.4.9.4 mower-control path.

## 2.4.9.5-beta2 — 2026-09-29

- Adds exact announcement targeting for one or more installations using the existing random minimal-presence installation ID.
- Keeps the identifier privacy-preserving: no mower serial number, account data, map, credentials or Voice Store robot fingerprint is sent with the feed request.
- Works with Reporting Server 1.0.37, whose message editor dynamically lists the currently reported mower models and installations and supports multiple selections.
- Preserves all 2.4.9.5-beta1 message caching, unread badges, one-time popup behavior, 23 languages and the stable 2.4.9.4 mower-control path.

## 2.4.9.5-beta1 — 2026-09-29

- Adds a separately testable **Újdonságok / News** panel and unread badge to the Anthbot Map Card without changing the stable 2.4.9.4 mower-control path.
- Adds a cached, best-effort announcement receiver. Feed failures keep the last valid messages and never block mower setup, commands, map rendering or settings synchronization.
- Supports remotely published news, releases, maintenance notices, service notices and voice-pack messages, with optional version/model targeting, expiry, links and one-time important popups.
- Keeps normal messages inside the News panel; only messages explicitly marked for popup display can open a one-time dialog.
- Stores read and popup-seen state locally in Home Assistant and updates notification badges without rebuilding or closing an open robot/zone settings panel.
- Sends only the installed Anthbot Map version, selected card language and mower model names when retrieving the feed; no mower serial, map, account data, credentials or installation identifier is included.
- Adds localized News UI text for all 23 supported card languages.

## 2.4.9.4 — 2026-09-28

- Rebuilds the M9/M9 Pro settings synchronization on the stable 2.4.9.3 base without replacing the existing Genie command path.
- Keeps global, manual-zone and automatic-zone settings synchronized between Home Assistant and the ANTHBOT app, including per-zone cutting height and related zone controls.
- Updates open Robot settings controls in place when fresh mower data arrives, so background refreshes no longer close the settings page, collapse the selected section or require reopening the panel to see app-side changes.
- Extends the Information panel with the active or most recently stopped mowing target, its effective cutting height source, mowed area in square metres and a separate `HH:MM:SS` mowing duration.
- Keeps the displayed mowing target and session summary after stopping, and advances the visible seconds between the M9/M9 Pro's minute-level duration updates while correctly pausing and resuming the local timer.
- Adds the new information labels to all 23 supported frontend languages and keeps their typography consistent with the other Information rows.
- Links Community Voice Store pairing to a privacy-preserving anonymous robot fingerprint so the same mower can be recognized across Home Assistant installations without transmitting its raw serial number.
- Documents the fingerprint behavior in `PRIVACY.md`; the normal installation-presence heartbeat remains unchanged and does not receive the robot fingerprint.
- Preserves the stable 2.4.9.3 mower command routing, map rendering, calibration, schedules, firmware, voice-pack and performance behavior.
- Full release validation passed **420/420 unit tests**, JavaScript syntax checks and bundled-frontend mirror verification.

## 2.4.9.3 — 2026-09-26

- Fixes the 2.4.9.2 service-routing regression where presence-heartbeat runtime metadata in `hass.data["anthbot_map"]` could be treated as a coordinator list, causing `'bool' object is not iterable` when commands such as mowing-height changes were sent.
- Hardens coordinator discovery and config-entry service loops so non-list runtime metadata is ignored safely.
- Fixes last-entry unload cleanup so presence runtime metadata does not prevent global Anthbot Map services and the schedule engine from being cleaned up.
- Adds regression coverage for the presence-runtime routing case.
- No mower command payload, model-specific control, map rendering, calibration, voice-store, or other 2.4.9.2 behavior is changed by this hotfix.

## 2.4.9.2 — 2026-09-25

- **Major CPU/performance fix:** removes the geometry/path hot path behind issue #64 and avoids repeated expensive zone/path checks during live operation, dramatically reducing call volume and Home Assistant CPU load in the profiled mower workload.
- Adds **four new map-card layouts** — Classic, Modern, Compact and Fullscreen — while preserving the original 2.4.9.1 layout as **Origin**, for a total of **five selectable views**.
- Keeps the view selection browser/device-local so different dashboards can use different layouts without changing mower configuration.
- Restores the 2.4.9.1 Origin mobile behavior, including full-screen landscape usage and 90° rotation in portrait, while preserving calibration, the top status bar and the floating status display.
- Refines responsive layout spacing and hover labels: buttons that already contain text no longer duplicate it in tooltips, while icon-only controls retain explanatory tooltips.
- Adds mowed-area percentage to the information/status details in the new views.
- Adds the minimal privacy-conscious installation presence heartbeat used for aggregate installation/activity/version/model statistics. It sends only a stable random installation ID, the Anthbot Map version and mower model; detailed Reports remain opt-in.
- Preserves the 2.4.9.1 thread-safety, Voice Pack Recorder protection, voice-store and model-specific mower behavior.

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
