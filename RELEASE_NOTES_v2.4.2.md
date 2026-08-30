# Anthbot Map v2.4.2

## Custom button persistence and battery-guard fixes

- Adds Home Assistant-persisted, per-mower custom actions for the card controls
  while retaining YAML `button_actions` compatibility.
- Supports Home Assistant services, scripts, target entities, and previously
  configured action data without removing the original ANTHBOT fallback.
- Applies a newly selected charger smart plug to the restart-safe 55+1 minute
  anti-shutdown guard immediately.
- Keeps a running guard deadline unchanged for ordinary threshold edits.
- Safely normalizes invalid legacy battery threshold combinations before the
  battery-saver state machine uses them.
- Preserves the existing battery-saver UI, profiles, 23 translations,
  shared/separate RTK behavior, mower controls, and restart persistence.

