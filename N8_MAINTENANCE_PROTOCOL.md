# ANTHBOT N8 / MGS maintenance protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

This document records the app protocol only. Physical advanced-maintenance writes remain intentionally **disabled** in Home Assistant until they are validated on a real N8 with the owner physically present. Some of these commands move the cutter, cutter lift or chassis.

## `useDetection` maintenance surface

The current MGS hook exposes the following actions:

```text
autoDetectionAll
manualDetection
semiAutoDetection
checkMap
maintenanceOpen
maintenanceClose
cutterOpen
cutterClose
cutterHight
cutterLow
cutterMid
moveForward
moveBackward
moveStop
```

Recovered closures:

```text
#26799 -> autoDetectionAll
#26800 -> manualDetection
#26801 -> semiAutoDetection
#26805 -> maintenanceOpen
#26806 -> maintenanceClose
#26807 -> internal maintenance_ctrl helper
#26808 -> cutterOpen
#26809 -> cutterClose
#26810 -> cutterHight
#26811 -> cutterMid
#26812 -> cutterLow
#26813 -> moveForward
#26814 -> moveBackward
#26815 -> moveStop
```

`checkMap` is delivered through another state/helper path and is not treated as a write command here.

## Maintenance mode

Enter maintenance mode:

```json
{"cmd":"maintenance_switch","data":1}
```

Exit maintenance mode:

```json
{"cmd":"maintenance_switch","data":0}
```

## `maintenance_ctrl`

Low-level control shape:

```json
{
  "cmd":"maintenance_ctrl",
  "data":{"sub":"<operation>"}
}
```

| UI action | `sub` value |
| --- | --- |
| cutterOpen | `motor_ctrl_open` |
| cutterClose | `motor_ctrl_close` |
| cutterHight | `cutter_lift_high` |
| cutterMid | `cutter_lift_mid` |
| cutterLow | `cutter_lift_low` |
| moveForward | `chassis_ctrl_forward` |
| moveBackward | `chassis_ctrl_backward` |
| moveStop | `chassis_ctrl_end` |

### Repeated hold controls

The current app repeatedly sends at least the cutter-open and chassis movement operations while the corresponding UI action remains active. The relevant closures use `setInterval` / `clearInterval`; the app passes scalar `100` to the interval setup.

Do not reproduce these hold controls remotely until real-device behavior and stop/failsafe handling are verified.

`moveStop` sends:

```json
{"cmd":"maintenance_ctrl","data":{"sub":"chassis_ctrl_end"}}
```

and then clears the movement interval.

## Maintenance checks

The app uses `cmd: maintenance_check` for diagnostic/self-check flows.

Static evidence proves:

- `autoDetectionAll` constructs `["all"]` for the all-components path;
- `manualDetection` passes its caller-supplied component value;
- semi-automatic detection also uses `maintenance_check`, with additional local result handling;
- the app reads `check_states` from the result for UI display.

The exact complete request/result schema for every individual component is not yet considered proven enough for a Home Assistant control surface.

## Maintenance counters/status

The MGS app reads `robot_maintenance` percentage keys:

```text
rc_pecent
cl_pecent
ccp_pecent
```

The maintenance UI also uses:

```text
blade
bladeHours
camera
cameraHours
ele_sheet
ele_sheetHours
```

`ele_sheet` is the charging-station/contact maintenance item.

## Proven screen type -> reset ID data flow

The maintenance-detail navigation callbacks now prove the screen component types:

```text
blade             -> type 0
camera            -> type 1
station/contacts  -> type 2
```

The reset writer (HBC98 function `#27128`) does **not** pass these route types through unchanged. It maps them before publishing:

```text
type 0 -> reset_id 1
type 1 -> reset_id 2
type 2 -> reset_id 0
```

Therefore the exact semantic mapping is:

```text
Blade maintenance reset             -> reset_id 1
Camera maintenance reset            -> reset_id 2
Charging station/contact reset       -> reset_id 0
```

The reset command is:

```json
{
  "cmd":"robot_maintenance_reset",
  "data":{"reset_id":1}
}
```

with `reset_id` replaced by the component value above.

This matches the existing Home Assistant integration mapping in `button.py`:

```text
reset_blade_maintenance        -> 1
reset_camera_maintenance       -> 2
reset_dock_contact_maintenance -> 0
```

So the existing reset buttons already use the statically recovered IDs. N8 routing remains isolated through `n8_control.py`, which recognizes `robot_maintenance_reset` and preserves its data object.

The app subscribes to `robot_maintenance` around the reset path and includes success/timeout handling.

## Home Assistant exposure policy

The following distinction is important:

- maintenance **counter resets** now have a statically proven component/ID mapping and the existing HA buttons already match it;
- physical `maintenance_switch`, `maintenance_ctrl` movement/cutter actions and individual diagnostic checks still require live N8 validation before any new N8 UI is exposed.

N8 transport currently recognizes:

```text
maintenance_switch
maintenance_check
maintenance_ctrl
robot_maintenance_reset
```

Before exposing new physical writes, verify on a real N8:

1. entering/exiting maintenance mode;
2. component check request/result shapes;
3. cutter/chassis hold-command cadence;
4. stop behavior if connectivity is lost;
5. firmware state restrictions and safety interlocks.

Any live cutter/chassis test must be done only with the owner physically present at the mower.
