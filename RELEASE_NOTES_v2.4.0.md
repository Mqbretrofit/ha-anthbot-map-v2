# Anthbot Map v2.4.0

## Battery-saving mowing mode

This release adds an optional battery-saving mode for mower chargers connected
through a Home Assistant switch entity.

- Configure an upper charge limit, an idle maintenance restart level, and a
  separate recovery level for interrupted mowing tasks.
- When cloud task event `1021` confirms a low-battery return, the integration
  charges to the configured recovery level and resumes the remembered task.
- Full-map, manual-zone, automatic-zone, outer-edge, and dock-edge tasks started
  from Home Assistant are remembered with their task-specific parameters.
- Manual return and completed-task events do not restart mowing.
- Automatic charger switch-on temporarily mutes the mower and restores its
  previous volume afterwards.
- State is persisted so Home Assistant restarts do not lose the recoverable task
  or a temporarily saved volume.

The ANTHBOT cloud does not expose reliable live mowing progress. This feature
therefore uses confirmed cloud task events instead of estimating or fabricating
a progress percentage.

## New entities

- Cloud task event code
- Cloud task event text
- Cloud task event type
- Cloud task event time
- Battery saver mode switch

> The mode is optional and remains inactive until a charger switch is configured
> and Battery saver mode is enabled.
