# Anthbot Map v2.4.6-beta.7

Settings usability prerelease.

## Added

- Adds a proper **Anthbot Map settings** menu under the Home Assistant integration options.
- Adds a **Development and diagnostics** settings page with two normal on/off controls:
  - **Share anonymous usage statistics**
  - **Send automatic diagnostic reports**
- Both options can now be enabled or disabled again at any time without using Developer Tools YAML.
- The settings page reuses the same consent/reporting backend as the popup, including installation-ID handling and privacy safeguards.
- The read-only Developer Agent remains separate and is not changed by these two switches.

## Battery Saver

- Existing Battery Saver configuration remains available from the same integration settings menu.
- Multiple-mower installations still get a mower selector before Battery Saver settings.
- Existing Battery Saver options and all unrelated integration options are preserved.

## Included fixes

- Includes the beta.6 fix that separates reporting consent from Developer Agent consent.
- Includes the automatic diagnostics, manual **Export & send firmware diagnostics**, and Genie / M-series Device Log media probes from previous 2.4.6 prereleases.

## Compatibility

- Mowing controls, mapping, zones, history, Battery Saver behavior, Genie behavior and M-series behavior are intentionally unchanged.
- This is a prerelease for controlled testing.
