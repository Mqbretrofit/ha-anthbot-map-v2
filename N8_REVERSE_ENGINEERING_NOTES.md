# ANTHBOT N8 / MGS03 reverse-engineering notes

Status: static-analysis working notes for `feature/n8-support`.

These notes are intentionally separate from the release branches. They do **not** change `release/v2.4.6-beta.10`, do not modify the already published `v2.4.6-beta.11` tag, and do not enable unvalidated write commands.

## Sources used

- ANTHBOT Android app protocol reference generated from Hermes bytecode (`2.15.15`).
- Direct static analysis of the real ANTHBOT `2.15.16` Android XAPK. Its `index.android.bundle` is Hermes bytecode version 98.
- Direct DEX analysis of the 2.15.16 MGS native map bridge (`MGSMapViewManager`, `com.anthbot.mgs.map.A`, `t4/e`, `u4/h`, `v4/e`).
- N8 command surface isolated in `models/n8_control.py`.
- Official ANTHBOT localization/copy workbook containing explicit `mgs` / `MGS03` feature markers and current MGS03 error/event copy.
- Privacy-safe live shadow probes from other M-series devices, used only as shared-schema clues until N8 confirms them.

## Strong MGS03 / N8 hardware evidence

Official app copy explicitly tags grass-bag / deflector installation checks and related failure states as `MGS03` behavior.

Current N8 status adapter exposes:

- `_n8_dumping`
- `_n8_grass_bag_in_position`
- `_n8_grass_shield_in_position`

from the N8 `mode` / `robot_sta` and `grass_state` reports.

## Current 2.15.16 MGS settings transport: `device_config`

Direct HBC98 analysis identified the current MGS settings writer. Current UI settings are published as:

```text
cmd: device_config
data: { ...device_config fields... }
```

Confirmed current fields include:

```text
log_switch
indoor_switch
rain_switch
rain_continue_time
anti_loss_switch
anti_loss_radius
pobctl_switch
pobctl_level
volume
camera_switch
```

Older command-specific builders still exist in the bundle, but the current MGS settings path writes through `device_config`. The N8-only adapter translates shared Home Assistant calls without changing Genie/M5/M9/M9 Pro routing.

### Proven current payloads

```text
Rain:
  device_config {rain_switch: 0|1, rain_continue_time: <seconds>}

Anti-loss:
  device_config {anti_loss_switch: 0|1}
  device_config {anti_loss_radius: <integer>}

Visual obstacle detection:
  device_config {pobctl_switch: 0|1}
  device_config {pobctl_level: 0|1|2}
```

## Anti-loss / boundary security

Static 2.15.16 analysis proves:

- user-facing unit: **metres**;
- value is integer;
- minimum accepted value: **50 m**;
- current writer: `device_config.anti_loss_radius`.

No explicit maximum has been recovered, so the anti-loss radius Home Assistant number remains blocked. The N8 anti-loss on/off switch can use the proven current route.

## Child lock / `ui_lock`

Official MGS copy contains Child Lock: robot panel buttons are disabled while power and emergency-stop remain functional.

A live M9 Pro reports `device_config.child_lock_switch`, but direct 2.15.16 Hermes analysis found no literal `child_lock` or `child_lock_switch` string. `ui_lock` exists only in confirmed read/gating paths and blocks commands through `device_locked` / `DEVICE_LOCK_FORBID_COMMAND`.

Therefore `ui_lock` is **not** treated as proof of the Child Lock writer. No N8 Child Lock write entity should be exposed until a real N8 before/after capture identifies the exact field and command.

## Visual obstacle sensitivity

Static 2.15.16 analysis proves the numeric mapping:

- `0` = Low
- `1` = Medium
- `2` = High

The N8 adapter translates the existing shared obstacle command to current `device_config.pobctl_switch` / `device_config.pobctl_level` fields. A future N8-only UI can safely use named Low/Medium/High options after live path confirmation.

## Rain behavior

Shared Home Assistant input remains:

```text
ctl_rainer {switch: ..., continue_time: ...}
```

N8-only transport converts it to:

```text
device_config {
  rain_switch: ...,
  rain_continue_time: ...
}
```

## N8 grass dumping

Confirmed command surface includes:

- `start_dump`
- `stop_dump`
- `ctl_building_dump`
- `area_set`
- `ridable_area_set`

Home Assistant currently exposes only direct Start/Stop grass dumping buttons. Dumping-area write UI is still disabled pending live N8 validation.

### Remote dumping lifecycle

Direct HBC98 analysis proves:

```text
ctl_building_dump {state: build_dump_init}
ctl_building_dump {state: build_dump_continue}
ctl_building_dump {state: build_dump_finish}
ctl_building_dump {dump_grass_areas: [...], state: build_dump_set}
```

The first three paths use 10-second timeouts. `build_dump_set` uses a 120-second timeout and waits for the current `map.area_id` path to update.

### Exact native dumping-area object

DEX analysis of the MGS native map bridge proves that the React Native event serializer emits:

```json
{
  "vertexs": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
  "id": 500,
  "grassId": 500,
  "eid": -1,
  "remote": false,
  "disable": false,
  "warningType": 0
}
```

Important details:

- `vertexs` is the protocol spelling;
- each vertex is exactly `[int, int]`;
- `id` and `grassId` are emitted from the same integer native field;
- native `eid` defaults to `-1`;
- `remote` is boolean;
- `disable` is boolean;
- `warningType` is integer;
- the native parser requires `id` and `vertexs` and accepts optional `remote`, `eid`, `disable`;
- native `addGrass(id, name, isRemote)` stores a `name` for the map overlay, but the serializer used by the current write path does **not** emit `name`. HBC comparison code can still read `name`, so it is treated as optional/app-side metadata rather than a required current wire field.

### Exact coordinate transform

The native map converter labels map metadata as `resolution`, `minX` and `minY` and performs:

```text
x_mm = int((x_transformed * resolution + minX) * 1000)
y_mm = int((y_transformed * resolution + minY) * 1000)
```

Inverse:

```text
x_transformed = (x_mm * 0.001 - minX) / resolution
y_transformed = (y_mm * 0.001 - minY) / resolution
```

followed by the map matrix transform.

Therefore `vertexs` contains **map/world millimetre coordinates**, not pixels and not latitude/longitude.

### Official app geometry

The native map UI creates a dumping area with side length:

```text
mapOverlayScale / mapResolution * 1.5
```

so the real map/world footprint is **1.5 m x 1.5 m**.

The four corners are generated as left/top, right/top, right/bottom, left/bottom. If rotated, they are first rotated around the rectangle centre, then converted to millimetre integer pairs.

### ID range

The app allocates dump-area IDs with `getNewId(..., 500, 599)`, and the submit handler explicitly filters the same range. Dumping-area IDs are therefore **500..599**.

### Normal add/edit save: exact `area_set` payload

The native `topGrassAreaSubmit` event returns `nativeEvent.grasses`. The HBC handler forwards changed native objects unchanged to `updateGrassAreas(changedAreas, [])`.

`updateGrassAreas` wraps them as:

```json
{
  "dump_grass_areas": [...changed native grass objects...],
  "delete_dump_areas": []
}
```

and the generic area writer publishes:

```text
cmd: area_set
data: {
  dump_grass_areas: [...],
  delete_dump_areas: [...]
}
```

The `area_set` writer waits for `map.area_id` and uses a 30-second timeout.

### Delete save

The delete event exposes `nativeEvent.grassId`. The app calls:

```text
updateGrassAreas([], [grassId])
```

so `delete_dump_areas` is an array of integer dumping-area IDs.

### Remote save

Native remote creation emits `topReportRemoteGrass` with the same `nativeEvent.grasses` serializer output. The HBC handler passes that array directly to `setupRemoteGrass`, which sends:

```text
cmd: ctl_building_dump
data: {
  dump_grass_areas: [...native grass objects...],
  state: build_dump_set
}
```

Detailed static evidence is recorded in `N8_DUMP_PROTOCOL.md`.

### App-side dumping-area validation rules

Recovered UI/native rules include:

- cannot be on the lawn boundary;
- cannot be on an electronic bridge;
- cannot be inside a restricted/no-go area;
- cannot be around the charging dock;
- must be at least 1 m from the inner lawn boundary;
- cannot be within the 0.5 m strip immediately outside the boundary;
- must be fully inside the plot boundary;
- dumping-area centre cannot be outside the map;
- dumping areas must be more than 1 m apart;
- editing is blocked during incompatible tasks;
- remote creation must start with the mower inside the mapped area.

### Dumping-area writes still blocked from HA

The static object, coordinate transform and write payload are now recovered. What remains is **live validation**, not basic schema guessing. Before exposing writes we still need one real N8 before/after capture proving that:

1. the cloud accepts the recovered 2.15.16 payload unchanged;
2. `area_setting.json` persists the expected subset/shape;
3. `map.area_id` changes as expected;
4. the real mower applies the same coordinate frame and geometry;
5. validation/warning behavior is safe enough for a Home Assistant editor.

## N8 work modes

Current N8 branch exposes:

- `0` = Mulch
- `1` = Collect
- `2` = Sweep

through `param_set {work_mode: <0|1|2>}` and keeps the selector N8-only.

## Do Not Disturb / schedule transport

Direct HBC98 reconstruction now proves that current MGS/N8 schedule writes use:

```text
cmd: mow_regular
```

The full plan envelope is:

```text
{timezone, timezone_sec, value}
```

and the incremental envelope is:

```text
{timezone, timezone_sec, version, value}
```

where:

```text
timezone_sec = -Date().getTimezoneOffset() * 60
timezone = timezone_sec / 3600
```

The writer waits up to 10 seconds for its response.

The DND object is distinguished by `unlock == 0` and uses:

```text
start_time: caller supplied
end_time: caller supplied
active: caller supplied
unlock: 0
week: [1,2,3,4,5,6,7]
repeat: 1
workmode: 0
```

`dnd_set` is analytics only. The actual service command is `mow_regular`.

The current app enables incremental-plan behavior when mower firmware is at least `1.16.15` and enables plan end-time behavior at firmware `1.15.13` (app-version gates are already satisfied by 2.15.16).

The map-manager workflow also reads `time_setting.json`; the N8 adapter now extracts it **read-only** and records only a privacy-safe structural summary: top-level keys, entry key sets, counts, timezone metadata and version. Individual schedule times are not exported by this probe.

`mow_regular` is recognized by the N8 native transport, but no HA DND/schedule writer is exposed until a real N8 confirms which full/incremental schema its firmware uses.

See `N8_DND_PROTOCOL.md`.

## Border / charging-dock behavior

Official MGS UI contains Border Recharge and edge-return behavior. Relevant identifiers include `nest_edge_grass`, `nest_edge_grass_start_each_task`, `nest_param_set`, `near_chg_mow_ctl`, `nest_mow_start`, and `nest_mow_stop`.

Existing generic controls and N8-native routing remain unchanged; exact N8 dock parameter reporting still benefits from live validation.

## Mapping / multi-map

N8 map reading is confirmed through:

```text
map_manager_<SN>.tar.gz
  -> iot_map.bin
  -> area_setting.json
  -> time_setting.json
```

using `/device/v2/presigned_url`.

The archive supplies map geometry, custom/manual areas, region/auto areas, ridable areas, dumping areas and plan/DND settings. `multi_map_ctl`, `delete_sub_map`, map backup and restore paths exist in the app but mutation remains disabled pending exact payload/live validation.

## Maintenance

MGS UI exposes blade/cutter, camera and charging-contact maintenance. The physical command family includes `maintenance_switch`, `maintenance_check`, and `maintenance_ctrl`.

The reset data flow is now statically proven end-to-end. Screen route types are:

```text
blade             -> type 0
camera            -> type 1
station/contacts  -> type 2
```

The writer maps them to:

```text
Blade maintenance reset             -> reset_id 1
Camera maintenance reset            -> reset_id 2
Charging station/contact reset       -> reset_id 0
```

and publishes:

```text
cmd: robot_maintenance_reset
data: {reset_id: ...}
```

These IDs match the existing Home Assistant reset buttons. Physical cutter/chassis maintenance controls remain disabled until an N8 owner is physically present for safety and failsafe validation.

See `N8_MAINTENANCE_PROTOCOL.md`.

## N8/MGS03 error and event evidence

Current copy contains, among others:

- `E213` — deflector not detected
- `E212` — grass bag not detected
- `E211` — grass bag close error
- `E210` — grass bag open error
- `E206` — millimetre-wave sensor warning
- `E205` — blade installation issue
- `E806` — LiDAR blocked
- `E805` — high temperature / task paused
- `E804` — low temperature / task paused
- `E802` / `E803` — LiDAR anomaly
- `E801` — current task timed out
- `E807` — map creation failed
- `E420` — mowing-height adjustment error
- `E440` — grass dumping incomplete; 10-minute completion window before dock return
- `E106` — system communication error

These should enter an N8-specific error/event normalization layer only after the exact live N8 error field shape is captured.

## Privacy-safe N8 diff workflow

N8 diagnostics include an `n8_protocol` discovery block. Compare two exports with:

```text
python tools/compare_n8_protocol_reports.py before.json after.json
```

Change exactly one official-app setting between captures to isolate the reported field change.

## Highest-value next live N8 captures

1. full named `property` and `service` shadow while idle;
2. Child Lock before/after;
3. anti-loss radius before/after;
4. visual sensitivity Low/Medium/High report values;
5. map-manager archive before and after one dumping-area add/edit/delete;
6. read-only `time_setting.json` structure/version plus one DND before/after change;
7. state during `dumpgrass` and after a successful dump;
8. grass-bag / deflector transition;
9. one harmless maintenance-page reset only while the owner is physically present.

The highest remaining blockers are Child Lock write identification, live dumping-area persistence validation, DND full-vs-increment firmware confirmation, anti-loss maximum/range validation and exact live N8 error/status payloads.
