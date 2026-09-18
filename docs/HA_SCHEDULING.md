# ANTHBOT app scheduling and Home Assistant overrides

Anthbot Map 2.4.8.0 uses the mower's native ANTHBOT app schedule as the single source of truth. It mirrors those rules into a Home Assistant calendar and dashboard, and writes create/edit/delete changes back with the native planner command used by app 2.15.16.

The normal user interface is the **Schedule** tab of the Anthbot Map Card. It contains the next-mow summary, last mower event, timed override controls and the native weekly-rule editor. The HA actions documented below remain available for automations and advanced use.

App-visible fields are the enabled state, weekdays, start time, mowing mode, native zone IDs and cutting height. HA keeps only presentation and automation metadata locally: the rule name, calendar duration, weather entity, forecast guard and catch-up window. Editing an existing rule preserves unknown model/firmware fields. M5/M9/N8/Pion plans can also be read from `time_setting.json` when the property shadow omits `appointment`.

## Timed override

Use `anthbot_map.override_schedule` with the mower entity as target:

```yaml
action: anthbot_map.override_schedule
target:
  entity_id: lawn_mower.your_mower
data:
  action: mow
  duration_hours: 2
  mode: zone
  zones: "1,2"
  mow_height: 40
```

Supported actions are `mow`, `park` and `clear`. A `mow` override returns the mower to the dock when its duration expires. A failed initiating command clears the override instead of leaving a misleading active state.

## Native weekly zone schedule

Create or update a rule with `anthbot_map.add_ha_schedule`:

```yaml
action: anthbot_map.add_ha_schedule
target:
  entity_id: lawn_mower.your_mower
data:
  summary: Front garden
  schedule_id: front_garden
  weekdays: ["0", "3"]
  start_time: "09:00:00"
  mode: zone
  zones: "1"
  mow_height: 45
  duration_minutes: 90
  weather_entity: weather.home
  forecast_guard_hours: 2
  rain_probability: 50
  catch_up_hours: 8
  enabled: true
```

Monday is `0`; Sunday is `6`. Reusing the native `schedule_id` updates the existing app rule. Delete it with `anthbot_map.delete_ha_schedule`. The historical service names remain for automation compatibility, but they now operate on the ANTHBOT app plan rather than a second HA-owned plan.

Rules can also be created in the HA calendar UI. Optional mower fields go in the description, separated by semicolons:

```text
mode=zone; zones=1,2; height=40; weather=weather.home; forecast=2; catchup=8
```

## Weather behavior

When a weather entity is configured, a rainy current condition makes HA return the mower to the dock when that native appointment becomes due. If `forecast_guard_hours` is greater than zero, the integration also checks the hourly forecast and applies the same hold for rain, pouring, hail, lightning-rain, snow or snow-rain, or a precipitation probability at/above `rain_probability`.

When `catch_up_hours` is greater than zero, a weather-blocked rule remains pending until that deadline. Conditions are checked again every five minutes. The mower starts once when conditions clear; after the deadline the run expires without starting.

## Entities and events

- `calendar.<mower>_schedule` — native ANTHBOT app rules plus the active HA override.
- `sensor.<mower>_next_mow` — next effective start; attributes include source, mode, zones, cutting height and any pending weather catch-up.
- `event.<mower>_mower_events` — native HA events suitable for automations.

Event types include `mowing_started`, `mowing_completed`, `stuck`, `error`, `rain_hold`, `docked`, `schedule_triggered`, `schedule_skipped`, `schedule_error` and `override_changed`.

The example dashboard in `examples/anthbot-dashboard.yaml` contains buttons for a two-hour mow, a six-hour park and clearing the override.
