# ANTHBOT Reports changelog

## 1.0.0-test.13

- Shows the new Anthbot Map v2.4.6-beta.13 automatic mower-error reports directly in the Reports dashboard.
- Displays `err_code`, its mapped description, `event_code`, `cloud_task_event_code`, mower mode/state and the privacy-filtered task-event message when available.
- Labels automatic mower-error uploads as `gyári hibariport` while keeping integration diagnostics and ordinary manufacturer reports visually distinct.
- Keeps the existing full diagnostic detail page unchanged, so every automatic error report can still be opened for the complete stored JSON.

## 1.0.0-test.11

- Adds the current Anthbot Reports diagnostics UI from Anthbot Map v2.4.6-beta.12.
- Shows robot identity/model directly in the diagnostics list.
- Distinguishes manufacturer-shareable reports (`gyári riport`) from Anthbot Map integration diagnostics (`integráció`).
- Adds the diagnostic detail route and lightweight diagnostics summary endpoint used by the dashboard.
- Fixes the Home Assistant App image packaging so `diagnostics_dashboard.py` and `diagnostic_detail.html` are included at runtime.
- Keeps the Reports app version independent from the Anthbot Map integration version so Home Assistant can offer Reports updates separately.
