# N8 validation test build — v2.4.6-beta.12

This branch is an isolated N8 validation build derived from `feature/n8-support`.

It is intended only for live ANTHBOT N8 / MGS03 testing and is not a normal release branch.

## Tester workflow

1. Install this branch/build and restart Home Assistant.
2. Confirm the mower is detected as N8 and wait for cloud/map state to settle.
3. Press the existing **Export & send firmware diagnostics** button once for the baseline.
4. Change exactly one setting in the official ANTHBOT app.
5. Wait for the state to settle, then press the diagnostics export button again.
6. Compare the two files with:

```text
python tools/n8_validation_bundle.py before.json after.json
```

For DND/dumping-area validation, add the corresponding before/after map-manager archives:

```text
python tools/n8_validation_bundle.py before.json after.json \
  --before-map before_map_manager.tar.gz \
  --after-map after_map_manager.tar.gz
```

See `N8_VALIDATION_WORKFLOW.md` for the exact test order and privacy rules.

## Safety boundary

The build keeps unvalidated/destructive writers disabled. In particular, it does not expose new Child Lock, DND, map backup/restore/delete, dumping-area edit, remote-drive, voice-pack or advanced-maintenance controls merely for testing.

`release/v2.4.6-beta.10` and the already-published `v2.4.6-beta.11` tag are not modified by this test build.
