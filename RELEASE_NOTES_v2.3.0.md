# Anthbot Map v2.3.0

## Mowing history

- Uses the confirmed mobile-app mowing-record endpoint.
- Shows completed sessions as readable cards with area, progress, duration,
  mode, source, and zone information.
- Opens per-session area, map, and path detail directly from the card.
- Find it under **Anthbot Map card → Diagnostics → Previous mowing tasks**;
  select a completed session to open its available visual detail.
- Corrects the historical MGS v1 coordinate scale.
- Filters known blade-off travel segments from the coverage view while keeping
  a safe fallback for files without usable point types.

## M5/M9 compatibility

- Adds experimental property-shadow normalization and live `curpath` decoding,
  based on field data from an M9 mower.
- Improves status, error, command, map-archive parsing, and wake handling
  without changing Genie routing.
- **Known limitation:** map display is not yet working on M5/M9 mowers.

## Map alignment

- Renames **Robot alignment** to **Mowing path alignment** to clarify that it
  controls the robot-derived mowing layer.
- Applies offset, horizontal and vertical scale, and rotation to the complete
  mowing path and coverage independently from the robot icon.
- Provides separate calibration controls and YAML blocks for the robot and the
  mowing path.
- Makes the up, down, left, right, narrower, wider, shorter, and taller controls
  move every separately calibrated layer in the same visual direction as the
  map-alignment controls.
- Keeps robot-icon direction adjustment separate from mowing-path alignment.
- Corrects mirrored cloud heading on horizontal travel while preserving the
  already correct heading for vertical travel.
- Preserves legacy `robotCalibration.rotation` as an icon-direction correction;
  independent path rotation is stored under `mowingPathCalibration`.
- Prevents mowing-path rotation from distorting the path on non-square maps
  while preserving existing map-calibration behavior.

## Reliability and privacy

- Targets the correct mower when more than one mower is configured.
- Handles long mowing sessions without confusing seconds and milliseconds.
- Removes captured device identifiers from the source.
- Removes the remaining frontend debug logging from command confirmation.
- Completes the calibration and mowing-history translations for all 23
  supported languages without English fallback labels.
- Keeps bundled frontend assets and release versions consistent.
- Removes a duplicate `serial_number` entry from the charging-contact reset
  service definition and prevents duplicate YAML mapping keys from returning.
