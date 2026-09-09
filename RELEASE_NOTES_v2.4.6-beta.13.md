# Anthbot Map v2.4.6-beta.13

## Automatic robot error diagnostics

- Adds opt-in automatic manufacturer diagnostics for every newly active non-zero mower `err_code`.
- Captures new task-event errors (`code_type: error`) with the vendor event message and current mower context.
- Stores the error code together with `event_code`, `cloud_task_event_code`, mower mode/state, online state, firmware, position/path context and the latest task event.
- Deduplicates the same incident when `err_code` and its matching task event arrive in separate shadow updates.
- Rearms after an error clears, so the same error is reported again if it genuinely returns later.
- Automatic reports remain privacy filtered: raw mower serial and alias are omitted; the existing anonymous serial hash remains available for identifying the same mower across reports.
- No mower-control, map rendering, Battery Saver or model-specific control behavior is changed.
