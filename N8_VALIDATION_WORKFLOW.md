# ANTHBOT N8 live validation workflow

Status: tester workflow for `feature/n8-support`. This procedure is deliberately read-mostly and privacy-aware. Do not use destructive map, maintenance, remote-drive, Child Lock, DND or voice-pack writes from Home Assistant until the corresponding official-app capture has been validated.

## Goal

The static ANTHBOT 2.15.16 reverse engineering is largely complete. The remaining work is to prove which recovered MGS03 paths the real N8 firmware actually reports and accepts.

The normal Home Assistant button:

```text
Export & send firmware diagnostics
```

already writes a privacy-filtered local JSON report. For N8, the report includes the `n8_protocol` discovery block. The tester only needs to press this button before and after changing exactly one official-app setting.

A new helper combines those two reports and can optionally compare the matching `map_manager_<SN>.tar.gz` archives without printing lawn coordinates or schedule times:

```text
python tools/n8_validation_bundle.py before.json after.json
```

or with map-manager archives:

```text
python tools/n8_validation_bundle.py before.json after.json \
  --before-map before_map_manager.tar.gz \
  --after-map after_map_manager.tar.gz
```

Use `--json` when a machine-readable result is preferred.

The dedicated hardware-test branch is:

```text
test/n8-validation-beta.12
```

Its manifest version is `2.4.6-beta.12`. CI packages an artifact named `anthbot-n8-validation-beta.12` containing the integration, this guide and the validation comparer. The branch's unit-tests, HACS, hassfest and package job are expected to stay green before an artifact is handed to a tester. It is not a normal release and does not alter the beta.10 branch or published beta.11 tag.

## Baseline capture

With the N8 online and idle:

1. wait for Home Assistant to show the mower online and for the map to finish loading;
2. press `Export & send firmware diagnostics` once;
3. keep the generated JSON as `baseline.json`;
4. record the N8 firmware version shown in the report;
5. if map/DND/dumping validation is planned, save the current `map_manager_<SN>.tar.gz` as the matching baseline archive.

Do not reuse the existing M9 Pro `1.0.42` capture as an N8 firmware baseline. The actual N8 firmware must come from the N8 itself.

## One-change rule

For every test below, change exactly one thing in the official ANTHBOT app, wait for the mower/cloud state to settle, then export the second diagnostics report. This makes the diff attributable to one control.

Recommended order:

### 1. Child Lock

- baseline diagnostics;
- official app: Child Lock OFF -> ON;
- second diagnostics;
- compare;
- optionally repeat ON -> OFF.

Expected outcome: identify the exact N8 reported field and, if service-shadow traffic is also captured, the exact writer. Do not infer `ui_lock`; static analysis proves that it has different semantics.

### 2. Anti-loss radius

Use two known values in the proven 50..500 m range. The static writer is already known as `device_config.anti_loss_radius`; this live test checks the N8 report path and acknowledgement behavior.

### 3. Visual obstacle sensitivity

Change Low -> Medium -> High one step at a time. Static values are already proven as 0, 1, 2. The live diff checks the N8 report path.

### 4. Near-dock mowing and mowing delay

Toggle near-dock mowing once and separately change mowing delay between Off / 1 h / 2 h / 3 h. Static command payloads are known; the live diff checks `near_chg_mow_ctl` and `mow_delay_time` report behavior.

### 5. DND / schedule

Save both diagnostics and map-manager archive before changing one DND interval. Then make exactly one DND edit in the official app and save both again.

`n8_validation_bundle.py` reads `time_setting.json` locally and exports only:

- presence and top-level key names;
- entry count;
- DND vs appointment counts;
- entry key sets;
- plan `version` when present;
- hashes/fingerprints of entries and plan IDs.

It does **not** print start/end times, weekday selections or other personal schedule values.

### 6. Dumping-area persistence

Save the map-manager archive before and after exactly one official-app dumping-area action: add, edit or delete. Perform these as separate tests.

The helper reads `area_setting.json` and exports only structural evidence:

- list counts;
- dump-area IDs;
- object key sets;
- short SHA-256 geometry fingerprints;
- a fingerprint of `area_id`.

Raw lawn/dumping coordinates are not printed by the comparison output.

### 7. Optional second-round validation

After the core blockers above are closed, use the same one-change procedure for:

- RTK/NRTK/Auto mode acknowledgement;
- voice-package installation state/progress;
- map backup create/update/restore/delete;
- cleaning mode;
- advanced maintenance while the owner is physically present at the mower.

## Sharing captures

Preferred files to share back for analysis:

```text
before diagnostics JSON
after diagnostics JSON
validation diff output
optional before map_manager tar.gz
optional after map_manager tar.gz
```

The diagnostics exporter excludes credentials by default. The map-manager archives themselves can contain private lawn geometry and schedules, so share them only when needed; the generated validation diff is the privacy-safe artifact for normal review.

Never commit account passwords, AWS/cloud credentials, PIN codes, signed voice-package URL query strings or full raw location/map geometry to public fixtures.

## Completion criteria for core N8 support

Core live validation can be considered complete when we have:

- one genuine N8 idle baseline with actual N8 firmware;
- Child Lock exact report/write path;
- DND `time_setting.json` schema/version behavior on that firmware;
- dumping-area add/edit/delete persistence behavior;
- no regressions in Genie/M5/M9/M9 Pro routing;
- green unit-tests, HACS and hassfest.

The separate `release/v2.4.6-beta.10` branch and already-published `v2.4.6-beta.11` tag remain untouched by this validation workflow.
