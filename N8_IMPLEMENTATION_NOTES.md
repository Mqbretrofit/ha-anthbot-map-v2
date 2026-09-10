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

Static 2.15.16 XAPK analysis has now recovered the dumping-area write wire
format without enabling it yet:

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

Dumping-area editing is still intentionally not exposed in Home Assistant until
a real N8 before/after map-manager capture validates the recovered static wire
format against the cloud and confirms the persisted `area_setting.json` shape.

Still intentionally not enabled until live N8 validation or the remaining
payload work is complete: PIN write, DND, voice-pack control, map backup writes,
advanced maintenance control, and dumping-area editing.
