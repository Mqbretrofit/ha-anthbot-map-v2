# ANTHBOT N8 / MGS03 reverse-engineering notes

Status: static-analysis working notes for `feature/n8-support`.

These notes are intentionally separate from the release branches. In particular, they do **not** change `release/v2.4.6-beta.10` and do not enable unvalidated write commands.

## Sources used

- ANTHBOT Android app protocol reference generated from Hermes bytecode (`2.15.15`).
- N8 command surface already extracted from the `2.15.16` app and isolated in `models/n8_control.py`.
- Official ANTHBOT localization/copy workbook containing explicit `mgs` and `MGS03` feature markers and current MGS03 error/event copy.
- Privacy-safe live shadow probes from other M-series devices. These are used only as **shared-schema clues**, never as proof that N8 uses the same field until an N8 capture confirms it.

## Strong MGS03 / N8 hardware evidence

The official app copy explicitly tags the following as `MGS03`:

- grass bag / deflector installed check;
- failure state when the grass bag or deflector is not installed.

This confirms that the grass collector / deflector logic is not only a generic MGS UI path but belongs to the MGS03/N8 device family.

Current N8 status adapter already exposes:

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

This is useful because the newer N8/MGS app UI references the same feature families. It is **not yet proof** that N8 reports every field at exactly the same path. The N8 diagnostics discovery block therefore looks for these names without enabling writes from this evidence alone.

Notably, the likely Child Lock report field is `device_config.child_lock_switch` on M9 Pro. An N8 before/after capture will confirm whether N8 uses the same field.

## N8 grass dumping

Confirmed N8 command surface already isolated in `n8_control.py`:

- `start_dump`
- `stop_dump`
- `ctl_building_dump`
- `area_set`
- `ridable_area_set`

Current Home Assistant implementation safely exposes `start_dump` and `stop_dump` only.

The official MGS UI proves that N8 supports all of the following dumping-area behavior:

- one-click dumping;
- one or more dedicated dumping areas;
- manual/remote dumping-area creation;
- updating an existing dumping area;
- electronic-fence based dumping-area definition;
- automatic selection of the nearest dumping area;
- map-change invalidation of a previously configured dumping area.

App-side validation rules found for dumping areas:

- cannot be on the lawn boundary;
- cannot be on an electronic bridge;
- cannot be inside a restricted / no-go area;
- cannot be around the charging dock;
- must be at least 1 m from the inner lawn boundary;
- cannot be within the 0.5 m strip immediately outside the boundary;
- must be fully inside the plot boundary;
- dumping-area center cannot be outside the map;
- dumping areas must be more than 1 m apart;
- editing is blocked while an incompatible task is active;
- creation must start with the mower inside the mapped area;
- editing can pause the current task.

### Still blocked

Dumping-area **editing/writing** remains disabled until the exact `ctl_building_dump` / map-write object shapes are reconstructed and live-validated. Reading `dump_grass_areas` from `area_setting.json` is already implemented.

## N8 work modes

Current N8 branch exposes the app-derived work modes through `param_set.work_mode`:

- `0` = Mulch
- `1` = Collect
- `2` = Sweep

Write payload currently used:

```text
cmd: param_set
data: {work_mode: <0|1|2>}
```

This is isolated to N8 in the Home Assistant selector.

## Anti-loss / boundary security

Official MGS UI contains:

- anti-loss mode description;
- configurable boundary-security alarm distance.

The `2.15.16` N8 command surface contains:

- `anti_loss_switch`
- `anti_loss_radius`

Current integration exposes only the isolated N8 anti-loss on/off switch. `anti_loss_radius` remains read-only until the app's allowed range/step and exact user-facing units are confirmed.

The shared M9 Pro shadow clue reports `anti_loss_radius = 50`, proving that this family can report a concrete numeric radius, but that single value does not establish the N8 minimum, maximum, step or unit conversion.

## Child lock

The official MGS UI now contains a dedicated **Child Lock** feature.

Semantics from the app copy:

- enabling it disables the robot panel buttons;
- power and emergency-stop buttons remain functional.

A live M9 Pro reports `device_config.child_lock_switch`, which is now included as a candidate in the privacy-safe N8 diagnostics scanner. No N8 child-lock write command is enabled yet: first confirm the N8 reported path with an official-app before/after capture, then recover the exact 2.15.16 command/payload.

## Visual obstacle sensitivity

New MGS-specific app copy (2026-02-25 marker) defines three perception levels:

- High: also avoids small obstacles such as stepping stones / leaf patches;
- Medium: avoids common obstacles such as stone paths / patio edges;
- Low: only avoids larger non-grass areas such as patios / gravel.

The existing Home Assistant control path uses:

```text
cmd: perception_obstacle_ctl
data: {switch: 0|1, level: 0|1|2}
```

The N8 command adapter already permits this command. The shared M9 Pro shadow uses `device_config.pobctl_switch` and `device_config.pobctl_level`; an N8 live capture will show whether the same reported schema is used. Live N8 validation is still required to lock the numeric level-to-label order before replacing the generic `0..2` number entity with named options.

## Rain behavior

N8 has an isolated payload normalization for `ctl_rainer`:

Shared integration input:

```text
{switch: ..., continue_time: ...}
```

N8 app-native data object:

```text
{rain_switch: ..., rain_continue_time: ...}
```

Official MGS copy also confirms that map building is prohibited in rain/night and that the mower can automatically return to the charging station when rain/night is detected during map creation.

## Border / charging-dock behavior

Official MGS UI contains **Border Recharge** and describes return-to-dock behavior along the lawn edge.

The older Hermes index also contains:

- `nest_edge_grass`
- `nest_edge_grass_start_each_task`
- `nest_param_set`
- `near_chg_mow_ctl`
- `nest_mow_start`
- `nest_mow_stop`

Current integration already has generic edge-following-return and automatic-dock-mowing controls plus N8-native command routing for `nest_mow_start`/`nest_mow_stop` and `param_set`. Exact N8 mapping between the app's Border Recharge UI and the reported `rid_switch`/dock parameters should be verified from live N8 shadow data before declaring it complete.

## Mapping / multi-map

N8 map reading is confirmed through:

```text
map_manager_<SN>.tar.gz
  -> area_setting.json
```

using `/device/v2/presigned_url`.

This yields the current area definition, including custom/manual areas, region/auto areas, ridable areas and dumping areas.

The app/protocol also exposes:

- `multi_map_ctl`
- `delete_sub_map`
- multi-map archive/files;
- map backup / restore UI paths.

Map backup writes, restore writes, delete-sub-map and multi-map mutation remain disabled pending exact payload reconstruction and live validation.

## Maintenance

MGS UI exposes maintenance for:

- blade / cutter;
- camera;
- charging contacts.

Protocol identifiers include:

- `maintenance_reset`
- `robot_maintenance_reset`
- `maintenance_switch`
- `maintenance_check`
- `maintenance_ctrl`

The N8 transport layer recognizes the N8 maintenance command family, but advanced N8 maintenance writes remain intentionally disabled until exact component IDs / object shapes are confirmed.

## N8/MGS03 error and event evidence

Official current copy contains the following relevant codes/events:

- `E213` — Deflector not detected
- `E212` — Grass bag not detected
- `E211` — Grass bag close error
- `E210` — Grass bag open error
- `E206` — Millimeter-wave sensor warning
- `E205` — Blade(s) fallen off / blade installation issue
- `E806` — LiDAR blocked
- `E805` — High temperature; task paused until temperature normalizes
- `E804` — Low temperature; task paused until temperature normalizes
- `E802` / `E803` — LiDAR anomaly
- `E801` — Current task timed out
- `E807` — Map creation failed; remote-control mower back to dock and restart mapping
- `E420` — Mowing-height adjustment error
- `E440` — Grass dumping incomplete; user has a 10-minute completion window before dock return
- `E106` — System communication error

Additional current events include:

- pause and attach grass bag to continue;
- dumping area inaccessible;
- dumping area not configured;
- install grass bag;
- install deflector or grass bag;
- 4G recharge success.

These should be added through an N8-specific error/event normalization layer once the exact live N8 error field(s) are captured. The existing generic `err_code` mapping is numeric and should not be overloaded with string `E...` codes without evidence of the live payload shape.

## N8 commands currently known by the isolated transport

`n8_control.py` currently recognizes:

- mowing: `mow_start`, `mow_pause`, `mow_continue`, `stop_all_tasks`
- charging: `charge_start`, `charge_pause`, `charge_continue`
- zones: `custom_area_mow_start`, `custom_area_mow_stop`, `region_mow_start`, `region_mow_stop`, `ridable_mow_start`
- dock edge: `nest_mow_start`, `nest_mow_stop`
- point mowing: `mow_point`, `mow_point_stop`
- dumping: `start_dump`, `stop_dump`, `ctl_building_dump`
- area/map writes: `area_set`, `ridable_area_set`, `multi_map_ctl`, `delete_sub_map`
- anti-loss: `anti_loss_switch`, `anti_loss_radius`
- maintenance: `maintenance_switch`, `maintenance_check`, `maintenance_ctrl`, `robot_maintenance_reset`
- rain: `ctl_rainer`
- obstacle perception: `perception_obstacle_ctl`
- parameters: `param_set`
- volume: `volume_ctl`

Recognition in the transport is **not** the same as enabling a Home Assistant entity. Write controls should only be exposed when payload semantics and constraints are sufficiently proven.

## Privacy-safe N8 diff workflow

The feature branch now adds an `n8_protocol` block to N8 diagnostics only. It records a compact set of relevant reported values plus candidate field names while redacting credentials and PIN fields.

Use the included helper to compare two exports:

```text
python tools/compare_n8_protocol_reports.py before.json after.json
```

Recommended method:

1. Export N8 diagnostics with the robot idle.
2. Change exactly **one** setting in the official app.
3. Wait for the reported shadow to update.
4. Export N8 diagnostics again.
5. Run the diff helper.

This turns a Child Lock / anti-loss / sensitivity experiment into a short list of exact field changes instead of a manual full-shadow comparison.

## Highest-value next live N8 captures

When an N8 owner is available, the most useful read-only captures are:

1. full named `property` and `service` shadow reported state while idle;
2. same shadow immediately after toggling Child Lock in the official app;
3. same shadow after changing anti-loss radius;
4. same shadow after changing visual sensitivity High/Medium/Low;
5. map-manager archive before and after adding/editing one dumping area;
6. state during `dumpgrass` and after a successful dump;
7. one grass-bag open/close or deflector attach/detach transition;
8. one harmless app-side maintenance-page read/reset only when the owner is physically present.

These captures should let us finish child lock, anti-loss radius, named perception levels, dumping-area editing and the N8 error/status decoder without guessing.
