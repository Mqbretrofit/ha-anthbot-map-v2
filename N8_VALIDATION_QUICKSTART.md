# N8 validation quick start (Windows)

This is the short tester procedure for a real ANTHBOT N8.

## What the tester does

1. In Home Assistant press **Export & send firmware diagnostics** and keep the generated JSON as the BEFORE capture.
2. In the official ANTHBOT app change **exactly one** N8 setting or perform exactly one N8 action.
3. Wait until the mower/cloud state settles, then press **Export & send firmware diagnostics** again and keep the generated JSON as the AFTER capture.
4. Double-click **`N8_VALIDATION_START.cmd`**.
5. Drag the BEFORE and AFTER JSON files into the two prompts.
6. Send back **both** generated files: `n8_validation_diff.json` and `n8_validation_summary.txt`.

The summary automatically groups changed paths into likely N8 feature areas (for example Child Lock, anti-loss radius, obstacle sensitivity, DND or dumping area). This is only a triage hint: no path is treated as proven until a genuine N8 capture confirms it.

For map/DND/dumping validation, also keep the matching BEFORE and AFTER `map_manager_*.tar.gz` archives and run:

```powershell
.\tools\n8_validation_windows.ps1 `
  -Before before.json `
  -After after.json `
  -BeforeMap before_map_manager.tar.gz `
  -AfterMap after_map_manager.tar.gz
```

The generated diff is designed to avoid printing raw lawn coordinates, schedule times, credentials or PIN codes.

## One-change rule

Never change two settings between captures. A clean before/after pair must represent one change only, otherwise the resulting diff cannot reliably identify the N8 field or acknowledgement path.

## Recommended first validation order

1. Child Lock OFF -> ON
2. Anti-loss radius between two known values
3. Visual obstacle sensitivity Low -> Medium -> High
4. Near-dock mowing toggle
5. Mowing delay Off / 1 h / 2 h / 3 h
6. DND edit with matching map-manager archives
7. Dumping-area add, edit and delete as three separate tests

The dedicated tester branch/build is `test/n8-validation-beta.12` / `2.4.6-beta.12`. It is isolated from the normal release branches.
