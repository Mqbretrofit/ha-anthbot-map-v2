# Anthbot Map v2.4.6-beta.3

Developer-agent probe hotfix prerelease.

## Fixed

- Fixes `area_definition`, `ridable_area_definition`, `map_definition`, `map_archive`, and `path_definition` developer probes to use the authenticated account REST client instead of the shadow/MQTT client.
- Resolves the `AttributeError` seen in v2.4.6-beta.2 when running `area_definition` against Genie or M9 Pro.
- Adds a regression test that verifies these cloud/map/path probes stay on `coordinator.account_client`.

## Unchanged

- Existing mower control, mapping, Battery Saver, Genie and M-series behavior remains unchanged.
- Developer-agent execution remains opt-in, read-only and limited to the built-in whitelist.
- Reporting Server `1.0.0-test.6` remains compatible; no server update is required for this client-side hotfix.
