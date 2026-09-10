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
- Visual obstacle sensitivity mapping is statically proven as Low=0,
  Medium=1, High=2.
- N8 diagnostics/diff helpers exist for privacy-safe live protocol comparison.
- Read-only N8 `time_setting.json` extraction now runs from the same map-manager
  archive. It retains only structural summary data (counts, key sets,
  timezone/version), not individual schedule start/end times.
- A standalone privacy-safe `tools/summarize_n8_multi_maps.py` helper can now
  inspect API Explorer/raw-shadow JSON and report only backup count, IDs,
  timestamps and field names without copying MD5 values, filenames or URLs.

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
we can identify the live firmware schema/version without guessing.

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
only; no Home Assistant backup/restore/delete controls are exposed. New
regression coverage explicitly protects that policy.

See `N8_MULTI_MAP_PROTOCOL.md`.

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

The official MGS copy includes Child Lock and a live M9 Pro shadow exposes
`device_config.child_lock_switch`. However, the real 2.15.16 HBC98 bundle has no
literal `child_lock` / `child_lock_switch` writer. Its `ui_lock` references are
confirmed command-gating/read paths, not a proven Child Lock setting write.

A generic `device_config` publisher is present and accepts a dynamic data
object, but that alone is not evidence that `child_lock_switch` is a valid N8
write field. Therefore Child Lock remains intentionally disabled until a real
N8 official-app before/after capture identifies its reported field and exact
write route.

## Still intentionally blocked

Until live N8 validation or the remaining payload work is complete, keep these
writes disabled:

- PIN write;
- DND/schedule write;
- Child Lock write;
- voice-pack control;
- map backup/restore/update/delete and sub-map deletion;
- advanced physical maintenance controls;
- dumping-area editing;
- anti-loss radius HA write until its upper range/validation is confirmed.

The published `v2.4.6-beta.11` tag and the separate
`release/v2.4.6-beta.10` branch are not part of this ongoing feature work and
remain untouched unless explicitly requested.
