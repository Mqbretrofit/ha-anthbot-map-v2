# Anthbot Map v2.4.6-beta.12

Pre-release focused on diagnostics/reporting improvements.

- Separates manufacturer-shareable mower/firmware reports from Anthbot Map integration diagnostics.
- Keeps integration-only map/path definition and live-shadow errors out of manufacturer reports.
- Adds report categorization in Anthbot Reports: `gyári riport` vs `integráció`.
- Shows the robot identity/model directly in the diagnostics list so reports can be matched to the correct mower without opening them.
- Preserves detailed integration diagnostics for map/path definition failures, including safe redacted metadata.
- Includes regression tests for report categorization and robot identity display.
