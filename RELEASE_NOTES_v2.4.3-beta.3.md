# Anthbot Map v2.4.3-beta.3

This beta is based directly on **v2.4.3-beta.2** and preserves its existing functionality.

## Changes

- Added per-zone **Mowing mode** selection:
  - **Normal** → `mow_mode = 0`
  - **Efficient** → `mow_mode = 1`
- Removed the incorrect zone **Edge cutting → mow_mode** mapping.
- Added app-style **Normal / Efficient** buttons to zone settings.
- Added a responsive information popup explaining both modes.
- The Efficient-mode help highlights that **the mower also cuts the zone edge**.
- Added the mowing-mode help text in all 23 supported languages.
- Fixed mobile button overlap and unified the popup appearance on mobile and desktop.
- Updated frontend cache keys so the new UI and translations load reliably.

## Compatibility

All unrelated v2.4.3-beta.2 functionality is retained. Diagnostic-only mowing-speed/shadow test sensors from the temporary test branch are not included in this release.
