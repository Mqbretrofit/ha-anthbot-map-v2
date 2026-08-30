# Anthbot Map v2.4.2

## Custom button persistence and battery-guard fixes

- Adds Home Assistant-persisted, per-mower custom actions for the card controls
  while retaining YAML `button_actions` compatibility.
- Supports Home Assistant services, scripts, target entities, and previously
  configured action data without removing the original ANTHBOT fallback.
- Applies a newly selected charger smart plug to the restart-safe 55+1 minute
  anti-shutdown guard immediately.
- Changing the battery-saver percentage thresholds does not reset timers that
  are already running.
- Invalid settings left over from previous versions are automatically corrected
  to safe values.
- Preserves the existing battery-saver UI, profiles, 23 translations,
  shared/separate RTK behavior, mower controls, and restart persistence.

