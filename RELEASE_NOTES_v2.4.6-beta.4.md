# Anthbot Map v2.4.6-beta.4

Diagnostic and developer-test prerelease.

## New in this beta

- Adds a temporary M5/M9/M9 Pro Device Log / media probe for investigating whether ANTHBOT exposes diagnostic images, video references, S3 object keys, filenames or other media metadata after `log_upload`.
- Adds the same isolated Device Log / media probe for Genie models.
- Keeps the M-series and Genie probes separate so one family cannot accidentally target the other.
- Probe output is stored locally as JSON and redacts credential-like fields, signed URL query strings and location fields before writing the report.
- If the probe itself enables Device Log, it attempts to restore the original OFF state after capture.

## Diagnostics reporting

- The existing firmware diagnostics export still saves the JSON report locally.
- The manual button is now named **Export & send firmware diagnostics** and also sends a privacy-filtered copy to the project diagnostics server with trigger `manual_export` when an installation ID is available.
- The server copy omits the plain mower serial number and alias and keeps the one-way serial hash for correlation.
- The entity exposes the last upload result (`sent`, `failed`, or `skipped_no_installation_id`).
- Existing automatic diagnostics for no-go/boundary crossings, mower errors, path/map failures and live-shadow errors remain available and unchanged.

## Safety / compatibility

- Existing mowing controls, mapping, zones, history, Battery Saver, Genie behavior and M-series behavior are intentionally preserved.
- The Device Log / media probes are diagnostic experiments only; they do not add or claim a live camera feature.
- This build is a prerelease intended for controlled testing before promotion to stable.
