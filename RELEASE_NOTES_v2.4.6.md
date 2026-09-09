# Anthbot Map v2.4.6

## Reporting and diagnostics

- Adds opt-in anonymous usage statistics for installation/model/version visibility.
- Adds opt-in automatic diagnostic reports for newly active mower errors and cloud task-event errors.
- Automatic error reports include the relevant mower state, firmware context, event/error codes and privacy-filtered diagnostic context to make real-world troubleshooting easier.
- Anonymous statistics and automatic diagnostics are controlled separately in **Anthbot Map → Settings → Development and diagnostics**.
- Both reporting options remain **disabled by default** and only send data after the user explicitly enables them.
- Reports are sent to the project-controlled ANTHBOT Reporting Server at `reports.mqbretrofithungary.online`, separate from ANTHBOT/TMT vendor infrastructure.

## N8 support — testing available

- N8-specific control, status, map/path handling and model-scoped entities are included and available for testing.
- The N8 implementation has been **code/API validated** with dedicated regression tests and model-isolation checks.
- **Real N8 hardware testing has not yet been completed.** N8 owners are welcome to test the integration and report model-specific behavior so the implementation can be verified against real devices.
- Existing Genie and M-series guards remain isolated; N8 support does not expand the existing M5/M9 model detection paths.

## Stability and compatibility

- Includes the tested v2.4.6 beta series, including automatic robot-error reporting from v2.4.6-beta.13.
- Preserves the working Genie and M-series controls, map/path/zone handling, mowing history, Battery Saver and runtime performance improvements from v2.4.5.
- Reporting is observer-only and does not alter mower-control behavior.
- Tested on real ANTHBOT Genie 1000 and M9 Pro hardware for the supported existing model paths.

## Validation

- Automated unit/regression tests.
- HACS validation.
- Home Assistant hassfest validation.
- JavaScript syntax and packaged frontend consistency checks.
- Final stable release candidate validation passed before publication.
