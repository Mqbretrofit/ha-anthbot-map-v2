# Anthbot Map v2.4.7.0

Architecture and stability release built on v2.4.6.6 and the field-tested v2.4.6.7 stability work.

## Live map architecture

- Separates high-frequency live map/path/pose delivery from the Home Assistant entity state machine.
- Adds a dedicated Home Assistant WebSocket transport for live map data.
- The card receives an initial full snapshot, then incremental path deltas instead of repeatedly receiving the complete path through entity attributes.
- Adds sequence tracking, automatic resync after gaps/mismatches, path-id reset handling, and rolling-window support for long M-series paths.
- Keeps a compatibility fallback: if the live frontend resource is unavailable, the legacy entity-based path remains usable instead of disabling map data.
- Prevents a stale frontend resource from taking over after downgrade when the backend no longer advertises live-stream support.
- Stops the card's legacy periodic `homeassistant.update_entity` polling for the Map entity while live-stream mode is active.

## Home Assistant Recorder and state load

- The Map entity is now a compact status/diagnostic anchor and no longer embeds full live `path`, `cloud_path`, `mowed_path`, or `pose` geometry while WebSocket live mode is active.
- Diagnostic collections such as map archive selection, task-event history and error-history snapshots no longer trigger a Map entity write every few seconds.
- Existing Map coordinator listeners are rebound to the compact write semantics when the live transport starts, preventing old Recorder wrappers from continuing to write at the previous cadence.
- `runtime_performance` remains visible live where needed but is excluded from Recorder attributes.
- A one-minute heartbeat keeps non-critical Map diagnostics current without turning live mowing into Recorder churn.

## No-Go and event-loop stability

- Moves expensive No-Go geometry evaluation off the Home Assistant event loop with `async_add_executor_job()`.
- Applies the protection to M-series, N8 and Genie path diagnostics.
- Uses stable geometry/path revision caching plus a live evaluation cadence guard so repeated cloud updates do not rescan unchanged geometry unnecessarily.
- Keeps path/pose forwarding and mower command routing unchanged.

## Validation

Field validation was performed on a real Anthbot M9 Pro with the live map open during mowing:

- live path and robot position continued updating through the WebSocket transport;
- the Home Assistant Map entity contained no full path/pose geometry while the path continued growing;
- Recorder load dropped from tens of Map state rows per three minutes to 3 rows in a 3-minute active-mowing sample;
- Home Assistant restart completed successfully and the full existing path returned after WebSocket reconnect/snapshot;
- movement, pause/resume and restart behavior remained functional;
- no Anthbot event-loop blocking or startup bootstrap timeout was observed in the tested flow.

Automated tests cover the WebSocket snapshot/delta protocol, resync behavior, rolling-window path handling, compact entity architecture, existing-listener rebinding, legacy polling suppression, Recorder semantics, M-series/N8 No-Go throttling and Genie path diagnostics. Home Assistant hassfest and HACS validation pass on the release candidate.

## Model scope

- M9 Pro: real-device field validation completed for the new live transport and Recorder behavior.
- M5/M9 family: shares the protected M-series path implementation.
- N8: dedicated model path/control handling remains separate; No-Go executor protection and N8-specific regression tests are included.
- Genie: dedicated path diagnostics remain separate; expensive No-Go diagnostics are moved off the event loop and covered by tests.

## Scope protection

No mower command-routing changes are introduced by this release. Genie, M5/M9-family and N8 control paths remain separated. The separate `Mqbretrofit/anthbot-reporting-server` project is not modified by this release.
