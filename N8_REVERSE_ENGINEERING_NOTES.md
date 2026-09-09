# ANTHBOT N8 / MGS03 reverse-engineering notes

Status: static-analysis working notes for `feature/n8-support`.

These notes are intentionally separate from the release branches. In particular, they do **not** change `release/v2.4.6-beta.10`, do not modify the already published `v2.4.6-beta.11` tag, and do not enable unvalidated write commands.

## Sources used

- ANTHBOT Android app protocol reference generated from Hermes bytecode (`2.15.15`).
- Direct static analysis of the real ANTHBOT `2.15.16` Android XAPK. Its `index.android.bundle` is Hermes bytecode version 98.
- N8 command surface isolated in `models/n8_control.py`.
- Official ANTHBOT localization/copy workbook containing explicit `mgs` and `MGS03` feature markers and current MGS03 error/event copy.
- Privacy-safe live shadow probes from other M-series devices. These are used only as **shared-schema clues**, never as proof that N8 uses the same field until N8 evidence confirms it.

## Strong MGS03 / N8 hardware evidence

The official app copy explicitly tags the following as `MGS03`:

- grass bag / deflector installed check;
- failure state when the grass bag or deflector is not installed.

Current N8 status adapter exposes:

- `_n8_dumping`
- `_n8_grass_bag_in_position`
- `_n8_grass_shield_in_position`

from the N8 `mode` / `robot_sta` and `grass_state` reports.

## Shared MGS shadow clues from a live M9 Pro

A current privacy-safe M9 Pro shadow probe exposes this `device_config` shape:

```text
device_config.anti_loss_radius
device_config.anti_loss_switch
device_config.camera_switch
device_config.child_lock_switch
device_config.indoor_switch
device_config.log_switch
device_config.pin_code
device_config.pobctl_level
device_config.pobctl_switch
device_config.rain_continue_time
device_config.rain_switch
device_config.volume
```

The same live probe also exposes:

```text
grass_state.grass_bag_in_position
grass_state.grass_shield_in_position
mapping_task.in_dump
```

This is a useful shared-schema clue, not proof that N8 reports every field at exactly the same path.

## Current 2.15.16 MGS settings transport: `device_config`

Direct HBC98 analysis identified the current MGS settings hook `useDeviceConfig` and its writer `toggleDeviceConfig`.

The current UI publishes settings as:

```text
cmd: device_config
data: { ...device_config fields... }
```

The current hook reads these fields:

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

Older command-specific builders such as `anti_loss_switch`, `anti_loss_radius`, `ctl_rainer` and `perception_obstacle_ctl` still exist in the bundle. However, the current MGS settings hook writes through `device_config`.

For compatibility with the shared integration API, the N8-only transport now converts the existing shared calls into the current app-native command without changing Genie/M5/M9/M9 Pro routing.

### Proven current payloads

Rain:

```text
cmd: device_config
data: {
  rain_switch: 0|1,
  rain_continue_time: <seconds>
}
```

Anti-loss switch:

```text
cmd: device_config
data: {anti_loss_switch: 0|1}
```

Anti-loss radius:

```text
cmd: device_config
data: {anti_loss_radius: <integer>}
```

Visual obstacle switch:

```text
cmd: device_config
data: {pobctl_switch: 0|1}
```

Visual obstacle sensitivity:

```text
cmd: device_config
data: {pobctl_level: <0|1|2>}
```

## Anti-loss / boundary security

Official MGS UI contains anti-loss mode and configurable boundary-security alarm distance.

Static 2.15.16 analysis now proves:

- user-facing unit: **meters** (`m`);
- value is parsed as an integer;
- minimum accepted value: **50 m**;
- current writer: `device_config` with `anti_loss_radius`.

The UI placeholder is `>=50m`, and invalid values below the minimum use the localized `safe_distance_limit` message with distance `50`.

No explicit maximum or step beyond integer input has been found yet. Therefore the existing N8 anti-loss on/off switch can use the proven `device_config` route, but a Home Assistant anti-loss-radius number entity remains intentionally blocked until an upper bound is proven or a safe unrestricted-input design is chosen and live-tested.

## Child lock / `ui_lock`

The official MGS copy contains a **Child Lock** feature whose semantics are:

- enabling it disables the robot panel buttons;
- power and emergency-stop remain functional.

A live M9 Pro reports `device_config.child_lock_switch`.

However, direct `2.15.16` Hermes analysis found **no literal `child_lock` or `child_lock_switch` string in the bundle**. The bundle does contain `ui_lock`, but all confirmed references are read/gating paths. `checkDeviceOnline` uses `ui_lock.value` to forbid commands and surfaces the `device_locked` / `DEVICE_LOCK_FORBID_COMMAND` state.

No `ui_lock` writer was found. Therefore `ui_lock` is a device/UI lock state but is **not proven to be the Child Lock setting**. No Child Lock Home Assistant write entity should be exposed until an N8 before/after capture identifies the reported field and exact official-app write path.

## Visual obstacle sensitivity

Static `2.15.16` analysis now proves the numeric option mapping exactly:

- `0` = **Low**
- `1` = **Medium**
- `2` = **High**

The option builder creates the values in the app with those IDs, and the low-level path has a dedicated warning before applying level `0`.

Official MGS descriptions:

- High: also avoids small obstacles such as stepping stones / leaf patches;
- Medium: avoids common obstacles such as stone paths / patio edges;
- Low: only avoids larger non-grass areas such as patios / gravel.

The shared Home Assistant control still calls:

```text
cmd: perception_obstacle_ctl
data: {switch: 0|1, level: 0|1|2}
```

For N8 only, the transport converts that to the current app-native `device_config` fields `pobctl_switch` and `pobctl_level`. Other mower families keep their existing route.

A future N8-only UI cleanup can replace the raw `0..2` number with named Low/Medium/High options without guessing.

## Rain behavior

The shared Home Assistant input is:

```text
cmd: ctl_rainer
data: {switch: ..., continue_time: ...}
```

For N8 only, the current transport converts it to:

```text
cmd: device_config
data: {
  rain_switch: ...,
  rain_continue_time: ...
}
```

Official MGS copy also confirms that map building is prohibited in rain/night and the mower can automatically return to the charging station when rain/night is detected during map creation.

## N8 grass dumping

Confirmed N8 command surface includes:

- `start_dump`
- `stop_dump`
- `ctl_building_dump`
- `area_set`
- `ridable_area_set`

Home Assistant currently exposes only `start_dump` and `stop_dump` as direct buttons.

Direct 2.15.16 HBC98 analysis has now reconstructed the outer dumping-area control protocol:

Create/init mode:

```text
cmd: ctl_building_dump
data: {state: build_dump_init}
```

Finish:

```text
cmd: ctl_building_dump
data: {state: build_dump_finish}
```

Continue:

```text
cmd: ctl_building_dump
data: {state: build_dump_continue}
```

Set dumping areas:

```text
cmd: ctl_building_dump
data: {
  dump_grass_areas: <area objects>,
  state: build_dump_set
}
```

The `build_dump_set` path uses a 120-second command timeout in the app.

The official MGS UI proves support for one-click dumping, dedicated dumping areas, manual/remote area creation, updating an area, electronic-fence based definition, automatic nearest-area selection and invalidation after map changes.

App-side dumping-area validation rules found:

- cannot be on the lawn boundary;
- cannot be on an electronic bridge;
- cannot be inside a restricted/no-go area;
- cannot be around the charging dock;
- must be at least 1 m from the inner lawn boundary;
- cannot be within the 0.5 m strip immediately outside the boundary;
- must be fully inside the plot boundary;
- dumping-area center cannot be outside the map;
- dumping areas must be more than 1 m apart;
- editing is blocked while an incompatible task is active;
- creation must start with the mower inside the mapped area;
- editing can pause the current task.

### Dumping-area writes still blocked

The outer command is now known, but the exact `dump_grass_areas` geometry/object schema still needs to be reconstructed and matched to a real N8 map archive. Therefore dumping-area editing/writing remains disabled. Reading `dump_grass_areas` from `area_setting.json` is already implemented.

## N8 work modes

Current N8 branch exposes:

- `0` = Mulch
- `1` = Collect
- `2` = Sweep

through:

```text
cmd: param_set
data: {work_mode: <0|1|2>}
```

This selector remains N8-only.

## Border / charging-dock behavior

Official MGS UI contains **Border Recharge** and describes return-to-dock behavior along the lawn edge.

Relevant protocol identifiers include:

- `nest_edge_grass`
- `nest_edge_grass_start_each_task`
- `nest_param_set`
- `near_chg_mow_ctl`
- `nest_mow_start`
- `nest_mow_stop`

Current integration already has generic edge-following-return and automatic-dock-mowing controls plus N8-native command routing for `nest_mow_start`/`nest_mow_stop` and `param_set`. Exact N8 mapping between the app's Border Recharge UI and reported dock parameters still benefits from live N8 validation.

## Mapping / multi-map

N8 map reading is confirmed through:

```text
map_manager_<SN>.tar.gz
  -> area_setting.json
```

using `/device/v2/presigned_url`.

This yields custom/manual areas, region/auto areas, ridable areas and dumping areas.

The app/protocol also exposes:

- `multi_map_ctl`
- `delete_sub_map`
- multi-map archive/files;
- map backup/restore UI paths.

Map backup writes, restore writes, delete-sub-map and multi-map mutation remain disabled pending exact payload reconstruction and live validation.

## Maintenance

MGS UI exposes maintenance for blade/cutter, camera and charging contacts.

Protocol identifiers include:

- `maintenance_reset`
- `robot_maintenance_reset`
- `maintenance_switch`
- `maintenance_check`
- `maintenance_ctrl`

The N8 transport recognizes the maintenance command family, but advanced N8 maintenance writes remain intentionally disabled until exact component IDs/object shapes are confirmed.

## N8/MGS03 error and event evidence

Official current copy contains relevant codes/events including:

- `E213` — Deflector not detected
- `E212` — Grass bag not detected
- `E211` — Grass bag close error
- `E210` — Grass bag open error
- `E206` — Millimeter-wave sensor warning
- `E205` — Blade installation issue
- `E806` — LiDAR blocked
- `E805` — High temperature; task paused
- `E804` — Low temperature; task paused
- `E802` / `E803` — LiDAR anomaly
- `E801` — Current task timed out
- `E807` — Map creation failed
- `E420` — Mowing-height adjustment error
- `E440` — Grass dumping incomplete; 10-minute completion window before dock return
- `E106` — System communication error

Additional current events include attach-grass-bag prompts, inaccessible/unconfigured dumping area and 4G recharge success.

These should be added through an N8-specific error/event normalization layer once the exact live N8 error field shape is captured. The existing generic numeric `err_code` mapping should not be overloaded with string `E...` codes without payload evidence.

## N8 commands recognized by the isolated transport

`n8_control.py` recognizes:

- mowing: `mow_start`, `mow_pause`, `mow_continue`, `stop_all_tasks`
- charging: `charge_start`, `charge_pause`, `charge_continue`
- zones: `custom_area_mow_start`, `custom_area_mow_stop`, `region_mow_start`, `region_mow_stop`, `ridable_mow_start`
- dock edge: `nest_mow_start`, `nest_mow_stop`
- point mowing: `mow_point`, `mow_point_stop`
- dumping: `start_dump`, `stop_dump`, `ctl_building_dump`
- area/map writes: `area_set`, `ridable_area_set`, `multi_map_ctl`, `delete_sub_map`
- current settings: `device_config`
- compatibility inputs translated N8-only: `anti_loss_switch`, `anti_loss_radius`, `ctl_rainer`, `perception_obstacle_ctl`
- maintenance: `maintenance_switch`, `maintenance_check`, `maintenance_ctrl`, `robot_maintenance_reset`
- parameters: `param_set`
- volume: `volume_ctl`

Recognition in the transport is **not** the same as exposing a Home Assistant entity. Write controls should only be exposed when payload semantics and constraints are sufficiently proven.

## Privacy-safe N8 diff workflow

N8 diagnostics include an `n8_protocol` discovery block. Use:

```text
python tools/compare_n8_protocol_reports.py before.json after.json
```

Recommended method:

1. Export N8 diagnostics with the robot idle.
2. Change exactly one setting in the official app.
3. Wait for the reported shadow update.
4. Export N8 diagnostics again.
5. Run the diff helper.

This turns a Child Lock / anti-loss / sensitivity experiment into exact reported-field changes instead of a manual full-shadow comparison.

## Highest-value next live N8 captures

1. full named `property` and `service` shadow reported state while idle;
2. before/after Child Lock toggle;
3. before/after anti-loss radius change;
4. visual sensitivity Low/Medium/High report values, mainly to confirm the reported path despite the numeric app mapping now being statically proven;
5. map-manager archive before and after adding/editing one dumping area, to recover the exact `dump_grass_areas` object schema;
6. state during `dumpgrass` and after a successful dump;
7. grass-bag open/close or deflector attach/detach transition;
8. one harmless maintenance-page read/reset only when the owner is physically present.

The highest remaining blockers are Child Lock write identification, dumping-area geometry schema, anti-loss maximum/range validation and exact live N8 error/status payloads.
