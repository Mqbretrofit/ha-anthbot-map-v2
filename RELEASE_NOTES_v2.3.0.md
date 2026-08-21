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

## Reliability and privacy

- Targets the correct mower when more than one mower is configured.
- Handles long mowing sessions without confusing seconds and milliseconds.
- Removes captured device identifiers from the source.
- Keeps bundled frontend assets and release versions consistent.
