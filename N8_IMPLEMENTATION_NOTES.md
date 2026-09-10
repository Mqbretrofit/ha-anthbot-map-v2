# N8 support work-in-progress

Base: `release/v2.4.6-beta.9`

This branch deliberately keeps Genie, M5, M9 and M9 Pro routing unchanged and
adds N8 through isolated model adapters.

Implemented in the first integration pass:

- N8 model-family detection and model boundary.
- N8-only service-shadow command transport.
- Existing full mow, pause, resume, stop and return-to-dock controls routed via
  the N8 app-style service shadow without Genie's `app_state` preamble.
- Existing manual-zone and auto-zone commands retained (`custom_area_mow_start`
  and `region_mow_start`).
- N8-only map-manager/`area_setting.json` adapter using the already proven MGS
  decoders while leaving M-series activation guards unchanged.
- N8-only Start grass dumping / Stop grass dumping button entities using
  `start_dump` and `stop_dump`.
- `dump_grass_areas` is loaded into the coordinator area definition for the
  next map-card rendering/editing pass.
- Current 2.15.16 MGS settings writes for anti-loss, rain and visual perception
  are translated N8-only to the app-native `device_config` command.
- Visual obstacle sensitivity mapping is statically proven as Low=0,
  Medium=1, High=2.

## Dumping-area write protocol

Static 2.15.16 XAPK analysis recovered the dumping-area write wire format
without enabling it yet:

- normal add/edit save uses `area_set` with
  `{dump_grass_areas: [...], delete_dump_areas: [...]}`;
- remote dumping-area setup uses `ctl_building_dump` with
  `{dump_grass_areas: [...], state: "build_dump_set"}`;
- native dump-area objects emitted to those writers contain `id`, `grassId`,
  `eid`, `remote`, `disable`, `warningType`, and `vertexs`;
- `vertexs` is an array of integer `[x, y]` pairs in millimetres;
- the standard app-created dumping area is a 1.5 m x 1.5 m square, represented
  by four possibly rotated corner points;
- dump-area IDs are allocated in the 500..599 range.

See `N8_DUMP_PROTOCOL.md` for the reconstructed wire schema.

Dumping-area editing is still intentionally not exposed in Home Assistant until
a real N8 before/after map-manager capture validates the recovered static wire
format against the cloud and confirms the persisted `area_setting.json` shape.

## Do Not Disturb

Static analysis now reconstructs the app's DND schedule object:

```text
start_time: caller supplied
end_time: caller supplied
active: caller supplied
unlock: 0
week: [1,2,3,4,5,6,7]
repeat: 1
workmode: 0
```

The plan/time pipeline uses `no_disturb`, `appointment`,
`delete_no_disturb`, and `delete_appointment`. The `dnd_set` string is proven
as an app logging/event identifier, not a proven mower-shadow command.

See `N8_DND_PROTOCOL.md` for details. DND remains disabled until the exact
current time/plan write endpoint and enclosing object are captured and verified.

## Maintenance

Static analysis now reconstructs most of the MGS maintenance command surface:

- `maintenance_switch` with scalar `1` / `0` enters/exits maintenance mode;
- `maintenance_ctrl` uses `{sub: ...}`;
- recovered `sub` values include cutter motor open/close, cutter lift
  high/mid/low, chassis forward/backward/end;
- `maintenance_check` drives the self-test flows; the all-components path uses
  `["all"]`;
- `robot_maintenance_reset` uses `{reset_id: ...}`;
- the maintenance screen has route types blade=0, charging contacts=1,
  camera=2, but static analysis has not yet directly proven that these values
  are passed unchanged as `reset_id`.

See `N8_MAINTENANCE_PROTOCOL.md` for exact recovered command shapes.

Advanced maintenance controls remain intentionally unexposed because several
commands physically move the cutter, cutter lift or chassis. Live verification
must be performed with the N8 owner physically present and must include stop /
failsafe behavior.

## Child Lock

The official MGS copy includes Child Lock and a live M9 Pro shadow exposes
`device_config.child_lock_switch`. However, the real 2.15.16 HBC98 bundle has no
literal `child_lock` / `child_lock_switch` writer. Its `ui_lock` references are
confirmed command-gating/read paths, not a proven Child Lock setting write.

Therefore Child Lock remains intentionally disabled until a real N8 official-app
before/after capture identifies its reported field and exact write route.

## Still intentionally blocked

Until live N8 validation or the remaining payload work is complete, keep these
writes disabled:

- PIN write;
- DND schedule write;
- Child Lock write;
- voice-pack control;
- map backup/restore and multi-map mutation;
- advanced maintenance controls;
- dumping-area editing;
- anti-loss radius Home Assistant write until its upper range/validation is
  confirmed.

The published `v2.4.6-beta.11` tag and the separate
`release/v2.4.6-beta.10` branch are not part of this ongoing static-analysis
work and must remain untouched unless explicitly requested.