# Anthbot Map v2.4.1

## Stable battery-saver release

- Adds three ready-made battery-care profiles — Maximum battery care,
  Balanced, and Always ready — plus fully adjustable custom settings.
- Persists the upper charge limit, idle recharge level, interrupted-task resume
  level, shared RTK power option, operating phase, and anti-shutdown timing for
  each mower. Home Assistant restarts no longer reset the active cycle.
- Adds the 55+1 minute anti-shutdown protection: while the mower is docked in
  standby with charger power off, the charger is enabled for one minute after
  55 minutes, then the cycle restarts.
- Shows anti-shutdown state and the next pulse countdown in the card, including
  initialization and active pulse states.
- Keeps normal maintenance charging separate from the short keep-awake pulse
  and avoids switching power blindly while mower telemetry is unavailable.
- Handles shared and separate RTK power correctly during mowing, return to dock,
  charging, and RTK initialization.
- Restores charger power immediately when Battery saver mode is disabled and
  preserves deliberate manual charging instead of treating it as an automatic
  battery-saver transition.
- Fixes integration unload/reload and applies saved settings to the running
  coordinator without requiring a Home Assistant restart.
- Keeps the Battery saver tile as a settings-dialog opener; the larger mode
  checkbox remains inside the dialog.
- Provides the complete battery-saver interface in all 23 supported languages.

This is the stable release that supersedes the `v2.4.1-beta` series.
