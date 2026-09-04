# Anthbot Map v2.4.3-beta.4

This beta builds on **v2.4.3-beta.3** and separates Genie, M5, M9 and M9 Pro model-specific behavior so changes for one mower family do not overwrite another family’s control path.

## Changes

- Split **Genie** and **M-series (M5/M9/M9 Pro)** model-specific behavior into dedicated layers while keeping the shared card and existing beta.3 functionality.
- Restored and improved **M9/M9 Pro boundary, mowing-path and zone handling**, including zones loaded from the map-manager `area_setting.json`.
- Aligned M-series start/pause/resume/stop routing with the observed official-app protocol; M9 Pro STOP uses `stop_all_tasks` with scalar `data = 1`.
- M-series zone mowing uses the selected zone ids, and the live selected zone can be tracked using `active_area.id`.
- Improved **M-series mowing-history zone association** and separation of live tasks from completed history. Position-based zone recovery remains only a conservative fallback for older incomplete records.
- Scoped card controls, settings and related entities to each mower serial number for safer multi-mower operation.
- Fixed **Genie live-status propagation** independently of the M-series layers.
- Hide controls that are not supported by the active mower model.
- Added model-specific mower images: **M9 Pro uses its own image**, **M9/M5 use the M9 image**, and the **existing Genie image is unchanged**.

## Beta note

The direct cloud source for the percentage shown by the official app in some M-series mowing-history rows is still under investigation. This beta does not claim that every old history percentage is already identical to the app.
