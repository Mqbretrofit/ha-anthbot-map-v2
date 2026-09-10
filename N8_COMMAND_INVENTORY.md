# ANTHBOT N8 / MGS command inventory

Status: static reverse-engineering inventory for `feature/n8-support`.

Source: direct analysis of the real ANTHBOT Android app `2.15.16` Hermes HBC98 bundle. This is an evidence/catalog file, **not** a request to expose every command in Home Assistant.

## Why this inventory exists

The 2.15.16 MGS code contains a central `DEVICE_LOCK_FORBID_COMMAND` array. It is used when `ui_lock.value == 1` to reject app commands that are not permitted while the device is locked. The array contains 31 concrete command strings and is therefore a useful independent inventory of active MGS command names.

Recovered list:

```text
mow_start
mow_pause
mow_point
mow_point_stop
charge_start
charge_pause
remote_ctl
factory_reset
ctl_mapping
area_set
custom_area_mow_start
custom_area_mow_stop
delete_map
delete_sub_map
ctl_building_forbid
mow_remote
exit_remote
ridable_mow_start
perception_obstacle_ctl
ctl_building_bridge
ctl_building_border
region_mow_start
region_mow_stop
clean_mode_cmd
nest_mow_start
nest_mow_stop
multi_map_ctl
nest_param_set
ctl_building_dump
start_dump
stop_dump
```

The bundle contains additional proven command constructors outside that lock list, including:

```text
mow_continue
stop_all_tasks
charge_continue
mow_regular
device_config
param_set
volume_ctl
voice_set
robot_maintenance_reset
maintenance_switch
maintenance_check
maintenance_ctrl
ctl_rainer
anti_loss_switch
anti_loss_radius
ridable_area_set
light_switch
ctl_cutter
ctl_near_chg_mow
mow_delay
local_time
sync_position
ctl_rtk_base
req_rtk_base_info
clear_err_code
clear_eve_code
req_all_path
req_history_mapping_path
req_dev_online
get_all_props
```

Some older command-specific builders coexist with newer `device_config` routes. Presence in this inventory does not prove that every command is used by every N8 firmware revision.

## Important reconstructed commands

### Light switch

The app contains this exact writer:

```json
{
  "cmd": "light_switch",
  "data": {
    "light_switch": 0
  }
}
```

or with value `1`.

The current settings screen exposes it only when `isLightSwitchEnabled()` is true. Static analysis of that gate shows it is enabled for debug/exhibitor/factory-style contexts, not normal production users. Therefore **do not add an N8 light switch merely because the command exists**.

### Global cutting height

The current MGS Device Settings screen reads direct `cutter_height` and uses a dedicated writer:

```json
{
  "cmd": "ctl_cutter",
  "data": 45
}
```

The `data` value is the selected integer height in millimetres. The production picker contains exactly `30, 35, 40, 45, 50, 55, 60, 65, 70` mm.

This is stronger than the earlier generic-constructor evidence: the complete screen -> modal -> save -> writer data-flow is now traced. The existing shared HA height entity already has the correct 30..70/5 range, so the N8-only transport translates the exact shared `param_set {cutter_height: value}` call to `ctl_cutter value`. Other mower families and other `param_set` fields are unchanged.

See `N8_CUTTER_TIME_SYNC_PROTOCOL.md`.

### Near-dock mowing control

The current MGS screen reads `near_chg_mow_ctl`. The switch is ON when that scalar equals `1`, and its handler sends the inverse current state. Exact payloads are therefore:

```json
{"cmd":"ctl_near_chg_mow","data":1}
{"cmd":"ctl_near_chg_mow","data":0}
```

The writer waits for the reported `near_chg_mow_ctl` and uses a 30-second timeout. This control is distinct from `nest_mow_start`/`nest_mow_stop` and from the around-dock parameter writer `nest_param_set`.

The command is recognized by the isolated N8 transport, but no new HA switch is exposed before live N8 validation.

See `N8_NEAR_DOCK_DELAY_PROTOCOL.md`.

### Mowing delay

The current MGS Rain & Delayed Mowing screen reads `mow_delay_time`. The value is in **minutes**. The exact 2.15.16 picker contains:

```text
Off     -> 0
1 hour  -> 60
2 hours -> 120
3 hours -> 180
```

The modal passes the selected scalar unchanged through the save callback. Exact payloads are:

```json
{"cmd":"mow_delay","data":0}
{"cmd":"mow_delay","data":60}
{"cmd":"mow_delay","data":120}
{"cmd":"mow_delay","data":180}
```

The writer waits for reported `mow_delay_time` and uses a 30-second timeout. The command is recognized by the isolated N8 transport, but no HA selector is exposed until a real N8 confirms the report shape/behavior.

See `N8_NEAR_DOCK_DELAY_PROTOCOL.md`.

### Cleaning mode

The bundle contains a fixed one-shot writer:

```json
{
  "cmd": "clean_mode_cmd",
  "data": 1
}
```

The current app only allows the corresponding wrapper while the mower is idle or paused. The exact physical behavior on N8 must be live-validated before exposure.

### Dock/nest parameter set

The current MGS `nest_param_set` writer builds a data object only from changed values among:

```text
cutter_height
mow_count
pobctl_switch
pobctl_level
```

and publishes:

```text
cmd: nest_param_set
data: {<changed fields>}
```

This is strong evidence that around-dock/charging-station mowing has its own height/count/visual-perception parameters.

### Local time

The current MGS `local_time` writer uses:

```text
cmd: local_time
data: {
  time_zone,
  year,
  month,
  day,
  hour,
  minute,
  second,
  week
}
```

Static data-flow proves:

- `time_zone = -Date.getTimezoneOffset() * 60`, in seconds;
- `year = fullYear - 2000`;
- `month = getMonth() + 1`;
- `day`, `hour`, `minute`, `second` are local time fields;
- `week` maps Monday=1 through Sunday=7 using `[7,1,2,3,4,5,6]` indexed by JavaScript `getDay()`.

No HA writer is needed at present.

### Position sync

`sync_position` is reconstructed separately from the normal service-shadow writers. It obtains phone location and writes:

```json
{
  "cmd": "sync_position",
  "data": {
    "lat": "<latitude as string>",
    "lon": "<longitude as string>",
    "time": "<Math.trunc(timestamp / 1000)>"
  }
}
```

Crucially, this path calls a lower-level `write` function and subscribes with `subscribeMessage`; it does **not** use the normal `publishDeviceCommand` path. Therefore `sync_position` must not be added to the cloud N8 transport without first identifying the local/BLE transport semantics.

See `N8_CUTTER_TIME_SYNC_PROTOCOL.md`.

## Feature gates recovered from 2.15.16

The app has explicit feature gates that combine application build/version and mower firmware.

### Map backup

`isMapBackupEnabled` requires, in the production paths reconstructed here:

```text
app version >= 2.8.0
mower firmware >= 1.15.0
```

The current 2.15.16 app therefore satisfies the app-side threshold; the N8 firmware still determines availability.

### Nest-edge / near-dock feature

`isNestEdgeEnabled` uses:

```text
app version >= 2.9.0
mower firmware >= 1.16.0
```

### Maintenance feature

`isMaintenanceEnabled` uses:

```text
app version >= 2.9.4
mower firmware >= 1.16.20
```

These thresholds are valuable when a live N8 owner reports that a feature shown in static code is absent in their official app UI.

## `ui_lock` is not Child Lock

Static analysis now gives a stronger reason not to map `ui_lock` to the MGS Child Lock feature.

When `ui_lock.value == 1`, the app's generic command guard checks the requested app command against `DEVICE_LOCK_FORBID_COMMAND` and raises the `device_locked` / `DEVICE_LOCKED` error for blocked commands. This is an **app-command/device lock** mechanism.

The official Child Lock copy, by contrast, describes disabling the mower's physical panel buttons while leaving power and emergency stop functional. Because the semantics are different and the 2.15.16 bundle contains no literal `child_lock` writer, `ui_lock` must not be repurposed as the Home Assistant Child Lock switch.

## Home Assistant policy

Commands already proven and live-safe can remain exposed through the isolated N8 adapter. Newly catalogued or destructive commands stay unexposed until their payload, firmware gate and real N8 behavior are validated.

In particular, keep these out of the public N8 HA control surface for now:

- factory reset;
- raw map/sub-map mutation;
- map backup restore/delete/update;
- manual/remote driving;
- mapping/building commands;
- physical cutter/chassis maintenance controls;
- debug/exhibitor light switch;
- `clean_mode_cmd` until its N8 behavior is confirmed;
- near-dock enable switch until its N8 behavior is confirmed;
- delayed-mow selector until live report shape/behavior is confirmed;
- Child Lock until its real writer is identified.
