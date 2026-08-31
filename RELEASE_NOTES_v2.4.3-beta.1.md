# Anthbot Map v2.4.3-beta.1

## Mowing progress, movable live status and configurable startup layout

This prerelease is based on v2.4.2 and preserves its existing battery-saver, custom-button, RTK, mower-control, translation and restart-persistence behaviour.

- Adds production `Mowing progress` and `Active zone area` sensors. The integration creates no `_test` progress entities.
- Calculates active-zone target area from mapped-area calibration and subtracts only the actual overlapping No-Go polygon area.
- Supports one or multiple selected mowing zones and full-area mowing.
- Shows the current mowing target and calculated percentage together with battery/status in a draggable live map badge whose position is saved.
- Treats a normally completed task at 95% or above as 100% and keeps that completion latched through charging/standby until a new mowing task starts.
- Recalculates mowing-history progress from mowed area and reconstructed net target area instead of blindly using the cloud's often-unhelpful 100% field.
- Includes PR #24 startup layout options: `default_panel`, `menu_open` and `default_submenu`.
- Keeps a temporary frontend lookup fallback for an old `_test` progress sensor during upgrade only; no new `_test` entity is created.
- Removes `mowing_progress` from legacy entity cleanup so the new production sensor survives restart/reload.

This is a beta prerelease for real-device validation before the next stable release.
