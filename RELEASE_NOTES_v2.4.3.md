# Anthbot Map v2.4.3

Stable release based on the field-tested v2.4.3 beta series, preserving existing Genie functionality while completing the model-specific M5/M9/M9 Pro support path.

## Highlights

- Separates **Genie** and **M-series (M5/M9/M9 Pro)** model-specific behavior so fixes for one mower family do not overwrite another family’s control path.
- Restores and improves **M9/M9 Pro boundary, mowing-path and zone handling**, including zones loaded from the map-manager `area_setting.json`.
- Aligns M-series start/pause/resume/stop routing with the observed official-app protocol; M9 Pro STOP uses `stop_all_tasks` with scalar `data = 1`.
- M-series zone mowing uses the selected zone ids and tracks the live selected zone via `active_area.id`.
- Improves **M-series mowing-history zone association** so the card can keep using its own calculated mowing percentage with the correct selected zone.
- Keeps conservative position-based zone recovery only as a fallback for older incomplete history rows.
- Scopes card controls, settings and related entities to each mower serial number for safer multi-mower operation.
- Fixes **Genie live-status propagation** independently from M-series behavior.
- Hides controls that are not supported by the active mower model.
- Restores model-specific mower images: **M9 Pro uses its own image**, **M9/M5 use the M9 image**, while the **existing Genie image remains unchanged**.

This release is published as the normal stable **v2.4.3** release, not as a beta or test build.
