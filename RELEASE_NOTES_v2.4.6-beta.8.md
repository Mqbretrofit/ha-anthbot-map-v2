# Anthbot Map v2.4.6-beta.8

Translation/runtime UI hotfix prerelease.

## Fixed

- Fixes blank rows in **Anthbot Map → Settings** where the Battery Saver and Development/Diagnostics menu arrows were visible but their labels were missing.
- Adds the required runtime translation files for this custom integration under `custom_components/anthbot_map/translations/`.
- Adds complete English runtime translations and Hungarian runtime translations for the current config/options/entity strings.
- The **Development and diagnostics** page now shows the two reporting switches with readable labels and descriptions.

## Why beta.7 showed blank labels

Home Assistant custom integrations load runtime localization from `translations/<language>.json`. The previous prerelease only updated `strings.json`, which is a Home Assistant Core build-time source and is not sufficient for a custom integration at runtime.

## Included from beta.7

- Integration settings menu with Battery Saver and Development/Diagnostics sections.
- User-changeable anonymous usage and automatic diagnostic-reporting toggles.
- Reporting consent remains separate from the read-only Developer Agent.
- Manual **Export & send firmware diagnostics**, automatic diagnostics, and Genie/M-series Device Log media probes remain included.

## Compatibility

- Existing mower control, mapping, zones, history, Battery Saver, Genie and M-series behavior are unchanged.
- This is a prerelease for controlled testing.
