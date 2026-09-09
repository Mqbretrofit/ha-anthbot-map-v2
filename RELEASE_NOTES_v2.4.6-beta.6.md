# Anthbot Map v2.4.6-beta.6

Reporting consent isolation hotfix prerelease.

## Fixed

- Separates the two reporting checkboxes from the independent read-only Developer Agent consent.
- Enabling the Developer Agent no longer marks usage-statistics / automatic-diagnostics consent as acknowledged.
- Repairs affected beta.1-beta.5 installations where `developer_agent_enabled: true` incorrectly suppressed the reporting popup while both reporting options were still disabled.
- Adds a dedicated reporting acknowledgement flag: `developer_reporting_opt_in_acknowledged`.
- Keeps the old shared acknowledgement value only as a compatibility migration signal; it no longer lets Developer Agent consent suppress reporting consent.
- The reporting backend no longer accepts or changes Developer Agent settings and no longer creates Developer Agent keys.

## Expected behavior after upgrading

For an affected installation with:

- `share_anonymous_usage: false`
- `send_automatic_diagnostics: false`
- `developer_agent_enabled: true`
- legacy `acknowledged: true`

`anthbot_map.developer_reporting_get` will report the reporting consent as not acknowledged for the new version, so the two-checkbox popup can appear again for an administrator.

## Included from beta.5 / beta.4

- Automatic registration of the reporting and Developer Agent consent UIs.
- M5/M9/M9 Pro Device Log / media diagnostic probe.
- Genie Device Log / media diagnostic probe.
- Manual **Export & send firmware diagnostics** action with local JSON plus privacy-filtered server upload when an installation ID is available.
- Existing automatic diagnostics for no-go/boundary crossings, mower errors, path/map failures and live-shadow errors.

## Compatibility

- Existing mowing controls, mapping, zones, history, Battery Saver, Genie behavior and M-series behavior are intentionally preserved.
- This is a prerelease for controlled testing.
