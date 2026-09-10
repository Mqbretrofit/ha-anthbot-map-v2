# ANTHBOT N8 / MGS maintenance protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

This document records the app protocol only. Advanced maintenance writes remain intentionally **disabled** in Home Assistant until they are validated on a real N8 with the owner physically present. Some of these commands move the cutter, cutter lift or chassis.

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

The recovered closures map as follows:

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
{
  "cmd": "maintenance_switch",
  "data": 1
}
```

Exit maintenance mode:

```json
{
  "cmd": "maintenance_switch",
  "data": 0
}
```

## `maintenance_ctrl`

The low-level control command uses this object shape:

```json
{
  "cmd": "maintenance_ctrl",
  "data": {
    "sub": "<operation>"
  }
}
```

Recovered `sub` operations:

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

Do not interpret that scalar beyond what static analysis proves here, and do not reproduce these hold controls remotely until real-device behavior and stop/failsafe handling are verified.

`moveStop` sends:

```json
{
  "cmd": "maintenance_ctrl",
  "data": {
    "sub": "chassis_ctrl_end"
  }
}
```

and then clears the movement interval.

## Maintenance checks

The app uses:

```text
cmd: maintenance_check
```

for its diagnostic/self-check flows.

Static evidence currently proves:

- `autoDetectionAll` constructs the one-element list `["all"]` for the all-components check path;
- `manualDetection` passes its caller-supplied component value into the check path;
- semi-automatic detection also uses `maintenance_check`, with additional local state/result handling;
- the app reads `check_states` from the result and maps returned entries for UI display.

The exact complete request/result schema for every individual component is not yet considered proven enough for a Home Assistant control surface.

## Maintenance counters/status

The MGS app reads `robot_maintenance` status with these percentage keys:

```text
rc_pecent
cl_pecent
ccp_pecent
```

The maintenance UI also uses the following component data:

```text
blade
bladeHours
camera
cameraHours
ele_sheet
ele_sheetHours
```

The current screen-navigation type mapping is statically recovered as:

```text
blade          -> type 0
charging sheet -> type 1
camera         -> type 2
```

Here `ele_sheet` is the charging-contact/sheet maintenance item shown by the app.

## Maintenance reset

The reset writer is reconstructed exactly as:

```json
{
  "cmd": "robot_maintenance_reset",
  "data": {
    "reset_id": "<value>"
  }
}
```

The app subscribes to `robot_maintenance` around this reset path and includes success/timeout handling.

Important: although the maintenance-page navigation types are proven to be `0`, `1`, and `2` as documented above, static analysis has **not yet directly proven** that those route `type` values are passed unchanged as `reset_id`. Keep the two facts separate until the data-flow is traced or a live N8 capture confirms it.

## Home Assistant exposure policy

The N8 transport already recognizes the following protocol family so future verified controls can remain N8-isolated:

```text
maintenance_switch
maintenance_check
maintenance_ctrl
robot_maintenance_reset
```

Recognition is not exposure. No new advanced maintenance button/switch should be added from this document alone.

Before exposing writes, verify on a real N8:

1. entering/exiting maintenance mode;
2. component check request/result shapes;
3. exact `reset_id` mapping;
4. cutter/chassis hold-command cadence;
5. stop behavior if connectivity is lost;
6. firmware state restrictions and safety interlocks.

The live movement/cutter tests must be done only with the owner physically present at the mower.