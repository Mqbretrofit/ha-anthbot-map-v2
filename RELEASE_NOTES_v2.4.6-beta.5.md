# Anthbot Map v2.4.6-beta.5

Consent UI hotfix prerelease.

## Fixed

- Restores automatic registration of the developer-reporting consent popup.
- The popup again shows the two optional checkboxes:
  - **Share usage statistics**
  - **Send automatic diagnostic reports**
- Restores registration of the separate read-only Developer Agent consent popup.
- Both consent UIs remain independent from account setup, mower control, map rendering and Battery Saver.

## Included from beta.4

- M5/M9/M9 Pro Device Log / media diagnostic probe.
- Genie Device Log / media diagnostic probe.
- Manual **Export & send firmware diagnostics** action, which still saves the JSON locally and sends a privacy-filtered server copy when an installation ID is available.
- Existing automatic diagnostics for no-go/boundary crossings, mower errors, path/map failures and live-shadow errors.

## Compatibility

- Existing mowing controls, mapping, zones, history, Battery Saver, Genie behavior and M-series behavior are intentionally preserved.
- This is a prerelease for controlled testing.
