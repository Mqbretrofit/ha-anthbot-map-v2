# Anthbot Map v2.4.6-beta.11

N8 validation prerelease based on `release/v2.4.6-beta.9`.

## Added

- Initial isolated ANTHBOT N8 / MGS03 model-family support.
- N8-specific command transport using the native app-style service-shadow flow.
- Full-area mowing, pause, resume, stop and return-to-dock routing for N8 without the Genie `app_state` preamble.
- Existing manual-zone and auto-zone mowing command routing for N8.
- N8 map-manager archive support with `area_setting.json` zone extraction using the proven MGS decoders.
- N8 mowing-path adapter.
- N8-specific status and history normalization.
- N8 rain payload normalization.
- N8 Start grass dumping and Stop grass dumping button entities.
- N8 dumping/grass hardware sensors.
- N8 mowing work-mode selector.
- N8 anti-loss switch.

## Isolation and compatibility

- N8 support is implemented through separate N8 adapters and explicit model boundaries.
- Genie, M5, M9 and M9 Pro routing remains protected by regression coverage.
- This prerelease is intentionally based on `v2.4.6-beta.9`; the separate `release/v2.4.6-beta.10` test branch is not included or modified.

## Validation

- GitHub Validate workflow passes on the N8 feature head before this release branch was created.
- Regression coverage includes N8 routing, map/zone isolation, mowing path, status/history, rain normalization, N8-only sensors, work mode and anti-loss controls.

## Still intentionally not enabled

The following N8 functions remain disabled until their live payload behavior is validated or the remaining protocol work is complete:

- PIN write
- Do Not Disturb configuration
- voice-pack control
- map backup writes
- advanced maintenance control
- dumping-area editing

## Testing status

This is a prerelease intended for live N8 owner testing before the N8 support is merged into the normal release line.
