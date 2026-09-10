# N8 support work-in-progress

Base: `release/v2.4.6-beta.9`

This branch deliberately keeps Genie, M5, M9 and M9 Pro routing unchanged and
adds N8 through isolated model adapters.

Implemented in the integration/reverse-engineering line:

- N8 model-family detection and model boundary.
- N8-only service-shadow command transport.
- Existing full mow, pause, resume, stop and return-to-dock controls routed via
  the N8 app-style service shadow without Genie's `app_state` preamble.
- Existing manual-zone and auto-zone commands retained (`custom_area_mow_start`
  and `region_mow_start`).
- N8-only map-manager/`area_setting.json` adapter using the already proven MGS
  decoders while leaving M-series activation guards unchanged.
- N8-only Start grass dumping / Stop grass dumping buttons using `start_dump`
  and `stop_dump`.
- `dump_grass_areas` is loaded into the coordinator area definition.
- Current 2.15.16 MGS settings writes for anti-loss, rain and visual perception
  are translated N8-only to the app-native `device_config` command.
- Anti-loss radius is statically proven as integer **50..500 m**, step 1 m, and
  is exposed only for N8 through the current `device_config` writer.
- Visual obstacle sensitivity mapping is statically proven as Low=0,
  Medium=1, High=2.
- N8 diagnostics/diff helpers exist for privacy-safe live protocol comparison.
- Read-only N8 `time_setting.json` extraction now runs from the same map-manager
  archive. It retains only structural summary data (counts, key sets,
  timezone/version), not individual schedule start/end times.
- A standalone privacy-safe `tools/summarize_n8_multi_maps.py` helper can inspect
  API Explorer/raw-shadow JSON and report only backup count, IDs, timestamps and
  field names without copying MD5 values, filenames or URLs.
- `N8_COMMAND_INVENTORY.md` records the broader current MGS command surface and
  feature gates without exposing unvalidated controls.
- Current 2.15.16 voice package listing, signed-URL request and complete
  `voice_set.data` payload are statically reconstructed. `voice_set` is now
  recognized by the N8 transport only; no public package selector is exposed.
- `models/n8_voice_payload.py` provides pure, non-publishing builders for the
  recovered voice command/signed-URL object so future live validation can use
  the exact wire shape without re-inventing it.
- `tools/n8_validation_bundle.py` combines before/after firmware diagnostics and
  optional before/after map-manager archives. It reports only structural
  changes, counts, field sets and short SHA-256 fingerprints; raw lawn geometry
  and personal schedule times are deliberately omitted from the diff output.
- `N8_VALIDATION_WORKFLOW.md` defines the exact one-change live test order for
  Child Lock, anti-loss, obstacle sensitivity, near-dock/delay, DND and dumping
  persistence validation.

## Dumping-area write protocol

Static 2.15.16 XAPK analysis recovered the dumping-area write wire format
without enabling it yet:

- normal add/edit save uses `area_set` with
  `{dump_grass_areas: [...], delete_dump_areas: [...]}`;
- remote dumping-area setup uses `ctl_building_dump` with
  `{dump_grass_areas: [...], state: "build_dump_set"}`;
- native dump-area objects contain `id`, `grassId`, `eid`, `remote`, `disable`,
  `warningType`, and `vertexs`;
- `vertexs` is an array of integer `[x, y]` pairs in millimetres;
- the standard app-created dumping area is a 1.5 m x 1.5 m square represented
  by four possibly rotated corner points;
- dump-area IDs are allocated in the 500..599 range.

See `N8_DUMP_PROTOCOL.md`.

Dumping-area editing is still intentionally not exposed until a real N8
before/after map-manager capture validates the persisted `area_setting.json`.

## Do Not Disturb / schedules

Static HBC98 analysis now proves the actual schedule service command:

```text
cmd: mow_regular
```

The full plan envelope is:

```text
{timezone, timezone_sec, value}
```

and newer firmware can use the incremental form:

```text
{timezone, timezone_sec, version, value}
```

The current app enables incremental plans when mower firmware is at least
`1.16.15`; end-time support is gated at firmware `1.15.13` for this app line.

The DND item itself has:

```text
start_time: caller supplied
end_time: caller supplied
active: caller supplied
unlock: 0
week: [1,2,3,4,5,6,7]
repeat: 1
workmode: 0
```

`unlock == 0` distinguishes DND from normal mowing appointments. `dnd_set` is
analytics only; it is not the mower command.

`mow_regular` is recognized by the N8 native transport so a future N8 plan
writer cannot fall through to legacy Genie routing. No HA DND/schedule writer
is exposed yet. The N8 map adapter probes `time_setting.json` read-only first so
we can identify the live N8 firmware schema/version without guessing.

Important: the available `1.0.42` firmware capture belongs to an **M9 Pro**, not
an N8, and must not be used to choose the N8 plan writer path.

See `N8_DND_PROTOCOL.md`.

## Multi-map / map backup / sub-map deletion

Static HBC98 analysis now proves the N8/MGS map-backup service command and its
nested data shape:

```text
cmd: multi_map_ctl
data: {sub_cmd: <operation>, id: <optional backup id>}
```

Recovered operations are:

```text
save_map      -> no id
update_map    -> id required by the UI flow
restore_map   -> id required by the UI flow
delete_map    -> id required by the UI flow
```

The app reads `multi_maps.map_list`, `multi_maps.state` and `multi_maps.time`.
Backup-list entries contain at least `id`, `map_file_name`, `md5`, and
`time_stamp`. A `state` value of `-1` is handled as failure.

A separate destructive sub-map command is also reconstructed exactly:

```text
cmd: delete_sub_map
data: {point: [[x1,y1], [x2,y2], ...]}
```

The command clones the incoming point pairs but performs no coordinate
conversion inside the writer. The upstream coordinate frame is therefore still
a live-validation blocker.

Both `multi_map_ctl` and `delete_sub_map` remain transport-recognized N8 commands
only; no Home Assistant backup/restore/delete controls are exposed. Regression
coverage explicitly protects that policy.

See `N8_MULTI_MAP_PROTOCOL.md`.

## Additional command/feature findings

The 2.15.16 MGS command guard exposes a 31-command device-lock list, giving us an
independent inventory of current command names. Newly catalogued commands include
`remote_ctl`, `factory_reset`, `ctl_mapping`, `ctl_building_forbid`,
`ctl_building_bridge`, `ctl_building_border`, `mow_remote`, `exit_remote`,
`clean_mode_cmd`, and `nest_param_set` in addition to the already isolated N8
surface.

Useful feature gates recovered from the app are:

```text
Map backup:   app >= 2.8.0, mower firmware >= 1.15.0
Nest edge:    app >= 2.9.0, mower firmware >= 1.16.0
Maintenance:  app >= 2.9.4, mower firmware >= 1.16.20
```

A `light_switch {light_switch: 0|1}` writer also exists, but its current feature
gate is restricted to debug/exhibitor/factory-style contexts, so it is not being
added as a normal N8 control.

See `N8_COMMAND_INVENTORY.md`.

## Maintenance

Static 2.15.16 data-flow reconstruction proves the reset mapping exactly:

```text
Blade maintenance reset             -> reset_id 1
Camera maintenance reset            -> reset_id 2
Charging station/contact reset       -> reset_id 0
```

These values already match the existing Home Assistant reset buttons. N8 routes
`robot_maintenance_reset` through its native service-shadow adapter.

The additional maintenance command family is also known:

- `maintenance_switch` with scalar `1` / `0` enters/exits maintenance mode;
- `maintenance_ctrl` uses `{sub: ...}`;
- known `sub` values cover cutter motor open/close, cutter lift high/mid/low,
  chassis forward/backward/end;
- `maintenance_check` drives the self-test paths.

Physical maintenance controls remain intentionally unexposed until an N8 owner
can validate them while physically present at the mower.

See `N8_MAINTENANCE_PROTOCOL.md`.

## Child Lock

The official MGS copy includes Child Lock and an M9 Pro shadow exposes
`device_config.child_lock_switch`. That capture is a shared-schema clue only;
it is not N8 confirmation.

Direct parsing of the real 2.15.16 HBC98 string/function tables now narrows the
static result further. `useDeviceConfig` (function 15857) reads exactly these
current MGS settings:

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

It creates the named setter closures `switchRainer`, `switchAntiLoss`,
`setAntiLossRadius`, `updateVolume`, `switchIndoor`, `switchLog`,
`switchVision`, `setVisionLever`, and `switchCamera`. There is no Child Lock
setter in this hook. Its associated selector function (27794) reads the same ten
`device_config` fields and no Child Lock field.

The complete Hermes string table and DEX string scan contain no literal
`child_lock` or `child_lock_switch`. This makes it unsafe to infer a writer from
the M9 Pro report field alone; the current 2.15.16 MGS settings hook simply does
not expose such a writer statically.

Static analysis also rules out `ui_lock`: when `ui_lock.value == 1`, the generic
app command guard rejects remote/app commands with `device_locked` /
`DEVICE_LOCKED`. That behavior is different from the official Child Lock
description, which disables the mower's physical panel buttons while leaving
power and emergency stop available.

Therefore Child Lock remains intentionally disabled until a real N8 official-app
before/after capture identifies its reported field and exact write route.

See `N8_CHILD_LOCK_PROTOCOL.md`.

## Live validation build

A separate `test/n8-validation-beta.12` branch is derived from this feature
branch for hardware validation only. Its manifest is marked `2.4.6-beta.12` and
its CI packages an `anthbot-n8-validation-beta.12` artifact containing the
integration plus the privacy-safe validation comparer and workflow notes. It is
not a normal release and does not retarget or merge PR #26.

## Still intentionally blocked

Until live N8 validation or the remaining payload work is complete, keep these
writes disabled:

- PIN write;
- DND/schedule write;
- Child Lock write;
- voice-pack control;
- map backup/restore/update/delete and sub-map deletion;
- manual/remote driving and map-building controls;
- advanced physical maintenance controls;
- dumping-area editing.

The published `v2.4.6-beta.11` tag and the separate
`release/v2.4.6-beta.10` branch are not part of this ongoing feature work and
remain untouched unless explicitly requested.
