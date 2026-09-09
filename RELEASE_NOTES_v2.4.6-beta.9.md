# Anthbot Map v2.4.6-beta.9

23-language runtime settings translation prerelease.

## Added

- Extends the Home Assistant **Anthbot Map → Settings** runtime translations from 2 languages to all 23 supported languages.
- The **Battery saver** and **Development and diagnostics** menu entries now have localized labels instead of blank or English-only rows.
- The two reporting controls and their descriptions are localized in all 23 languages:
  - anonymous usage statistics
  - automatic diagnostic reports
- Battery Saver option labels and validation messages are also localized in all 23 runtime language files.

## Supported Home Assistant locales

- English (`en`)
- Hungarian (`hu`)
- German (`de`)
- French (`fr`)
- Spanish (`es`)
- Italian (`it`)
- Portuguese (`pt`)
- Dutch (`nl`)
- Polish (`pl`)
- Czech (`cs`)
- Slovak (`sk`)
- Romanian (`ro`)
- Danish (`da`)
- Swedish (`sv`)
- Norwegian Bokmål (`nb`)
- Finnish (`fi`)
- Simplified Chinese (`zh-Hans`)
- Traditional Chinese (`zh-Hant`)
- Turkish (`tr`)
- Thai (`th`)
- Vietnamese (`vi`)
- Korean (`ko`)
- Khmer (`km`)

Home Assistant uses `nb`, `zh-Hans`, and `zh-Hant` as the runtime locale identifiers for Norwegian Bokmål and Chinese, so those filenames are used instead of the frontend aliases `no`, `zh-CN`, and `zh-TW`.

## Validation

- Adds an automated test that requires exactly these 23 runtime translation files.
- Every file is parsed as JSON and checked for the Battery Saver, Development/Diagnostics, anonymous usage, and automatic diagnostic-report labels.

## Compatibility

- No mower control, map, zone, history, Battery Saver logic, diagnostics transport, Genie behavior, or M-series behavior is changed.
- Includes all fixes and features from v2.4.6-beta.8.
- This is a prerelease for controlled testing.
