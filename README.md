# Anthbot Map for Home Assistant

[English](README.md) | [Magyar](README_HU.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![GitHub release](https://img.shields.io/github/v/release/Mqbretrofit/ha-anthbot-map-v2)](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/latest)
[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mqbretrofit&repository=ha-anthbot-map-v2&category=integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Unofficial Home Assistant integration and custom Lovelace map card for ANTHBOT robotic lawn mowers.

Anthbot Map connects Home Assistant to the ANTHBOT cloud, creates model-aware mower entities and bundles the `anthbot-map-card`. The card can display the mower, charging station, lawn boundary, mowing zones, no-go zones, live and historical mowing paths, calculated coverage and an optional aerial/drone photograph of the garden.

> [!WARNING]
> This is a community project and is not affiliated with ANTHBOT/TMT.

## Current stable version

**Anthbot Map 2.4.6.4**

- Release: [v2.4.6.4](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.6.4)
- HACS installs the latest stable GitHub release.
- The bundled frontend resource uses the matching `?v=2.4.6.4` cache key.

### What changed in 2.4.6.4

- Automatic diagnostics are now episode/edge triggered, so the same persistent `no_go_path_crossing` or other unchanged diagnostic condition is not uploaded repeatedly every hour.
- Existing diagnostic conditions are seeded at Home Assistant/integration startup, so a restart does not replay an old condition as a new report.
- Historical cloud task-event errors remain visible as history but now carry explicit fresh/stale metadata; an expired event no longer independently triggers a new automatic robot-error report.
- The AWS IoT live-shadow listener survives unexpected runtime/transport failures, reconnects with bounded backoff and rotates temporary IoT credentials after repeated reconnect failures.
- M-series map identity now keeps logical `map.map_id`, `area_id`, `plan_id` and the raster `map_id` embedded in `map_manager_<serial>.tar.gz` as separate protocol-layer identifiers.
- The M-series fallback no longer derives `map_manager_<map_id>.tar.gz` from a logical map id, and a valid serial-named map-manager is not repeatedly downloaded just because logical and raster IDs differ.
- Genie, M-series and N8 routing remain separated; normal mower-control payloads were not changed by this maintenance release.

### Recent 2.4.6.x releases

#### 2.4.6.3 — full read-only developer diagnostics

- Added opt-in `full_state`, `full_diagnostics`, `state_inspector`, `state_diff` and `refresh_diagnostics` Developer Agent probes.
- Added capability advertisement and safe server-side parameters so future field-level diagnostics normally do not require a new integration build.
- Read-only diagnostics do not permit arbitrary Python, arbitrary HTTP/MQTT, method/property execution or mower-control commands.
- Credential-like and sensitive fields remain redacted/protected.

#### 2.4.6.2 — reporting heartbeat hotfix

- When anonymous usage statistics are enabled, startup/reload sends a lightweight non-blocking heartbeat with the actually running integration version and already-approved anonymous metadata.
- No heartbeat is sent when anonymous statistics are disabled.

#### 2.4.6.1 — Developer Agent setting

- Added **Allow read-only developer requests** under **Anthbot Map -> Settings -> Development and diagnostics**.
- Anonymous usage statistics, automatic diagnostics and read-only developer access are three independent permissions.

#### 2.4.6 — reporting, diagnostics and N8 test support

- Added opt-in anonymous usage statistics and opt-in automatic diagnostic reports for newly active mower/task-event errors.
- Added N8-specific control, status, map/path handling and model-scoped entities for testing.
- N8 code/API paths are regression-tested and isolated from Genie and M-series detection.
- Existing Genie and M-series control/map/path/zone/history/Battery Saver behavior was preserved.

For older changes, see the [GitHub Releases](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases) page and [CHANGELOG.md](CHANGELOG.md).

## Supported models

| Model family | Status | Notes |
| --- | --- | --- |
| ANTHBOT Genie | Supported | Shared Genie path; real-device validation includes Genie 1000. |
| ANTHBOT M9 Pro | Supported | M-series map/control/status/history path; directly hardware-tested. |
| ANTHBOT M9 | Supported through shared M-series implementation | Not directly hardware-validated by this project yet. |
| ANTHBOT M5 | Supported through shared M-series implementation | Not directly hardware-validated by this project yet. |
| ANTHBOT N8 | Testing available | Model-specific code/API path is implemented and isolated; real N8 hardware validation is still required. |

> [!IMPORTANT]
> Model-specific behavior is intentionally separated. Genie, M5/M9/M9 Pro and N8 fixes should not be widened into another model family without protocol evidence.

## Main features

- ANTHBOT cloud login from the Home Assistant UI
- multiple mowers on one ANTHBOT account
- persistent AWS IoT/MQTT shadow updates plus cloud REST data
- resilient automatic MQTT reconnect handling
- native Home Assistant `lawn_mower` entity
- full-area, manual-zone and automatic-zone mowing
- outer-edge and dock-surroundings mowing where supported by the model
- pause, resume, stop and return-to-dock controls
- battery, charging, status, RTK, network, firmware and maintenance entities
- map, zone, task-event, error and diagnostic entities
- live mowing path and calculated mowing-coverage display
- previous mowing tasks with available area/map/path details
- model-specific map/path handling for Genie, M-series and N8 paths
- optional aerial or drone photograph as the map background
- fullscreen map, zoom, pan and rotation
- separate map, mower, mowing-path and decoded-boundary calibration
- per-mower custom card-button actions stored in Home Assistant
- Battery Saver and 55+1 minute Shutdown Guard for smart-plug-controlled chargers
- rain-aware Battery Saver/return handling
- generated YAML that can be copied from the card
- 23 interface languages
- optional anonymous usage reporting, automatic diagnostics and read-only Developer Agent access

## Battery Saver and Shutdown Guard

Battery Saver is optional and is intended for installations where the mower/RTK power supply is controlled by a Home Assistant `switch` entity.

It supports:

- per-mower persistent settings and operating state;
- **Maximum battery care**, **Balanced**, **Always ready** and fully adjustable custom profiles;
- configurable upper charge limit, maintenance-charge level and interrupted-task resume level;
- shared or separate RTK power handling;
- restart-safe state persistence;
- a **55+1 minute Shutdown Guard** that periodically restores charger power briefly while a docked mower is intentionally kept without charger power;
- rain-safe recovery behavior so rain-protection events do not force an inappropriate mowing resume.

Battery Saver settings are available from the card and are stored in Home Assistant.

## Development, reporting and diagnostics

Open **Settings -> Devices & services -> Anthbot Map -> Configure -> Development and diagnostics**.

The three permissions are independent and disabled unless the user enables them:

1. **Share anonymous usage statistics** — sends limited installation/model/version information to the project reporting server.
2. **Send automatic diagnostics** — sends privacy-filtered diagnostic context when a new supported error episode is detected.
3. **Allow read-only developer requests** — enables the opt-in Developer Agent used for remote read-only troubleshooting.

The project reporting endpoint is operated separately from ANTHBOT/TMT vendor infrastructure.

### Read-only Developer Agent

From 2.4.6.3 the Developer Agent supports generic diagnostics rather than one-off hard-coded field probes:

- `full_state` — complete credential-redacted reported state, including internal integration keys;
- `full_diagnostics` — full state plus safe runtime snapshots/object inventories;
- `state_inspector` — read selected nested paths under safe diagnostic roots;
- `state_diff` — create/reset a baseline and return changed reported-state paths;
- `refresh_diagnostics` — perform a read-only property refresh, then collect full diagnostics.

The diagnostic boundary deliberately excludes mower-control commands, arbitrary code execution, arbitrary files, arbitrary URLs, arbitrary HTTP/MQTT calls, Home Assistant-wide internals and credential/session objects.

## Using another ANTHBOT integration

Anthbot Map v2 uses its own `anthbot_map` integration domain, so an older ANTHBOT integration may remain installed for rollback. Do **not** enable two ANTHBOT integrations for the same mower at the same time.

> [!CAUTION]
> Do not run Anthbot Map together with `vincentjanv/anthbot_genie_ha`, the AdrianTIonut fork or another ANTHBOT Home Assistant integration. Concurrent integrations can open competing cloud sessions and send conflicting commands to the same mower.

Safe migration and rollback:

1. Leave the previous integration installed.
2. Disable its config entry under **Settings -> Devices & services**.
3. Restart Home Assistant.
4. Add and test **Anthbot Map**.
5. To roll back, disable Anthbot Map, enable the previous integration and restart Home Assistant.

Existing entity-registry entries can cause new entity IDs to receive an `_2`, `_3` or later suffix. This is expected and is not an integration error.

## Requirements

- Home Assistant 2024.1.0 or newer
- HACS for the recommended installation method
- a working ANTHBOT account
- internet access to the ANTHBOT cloud

# Installation

## Install with HACS

### 1. Add the custom repository

1. Open **HACS -> Integrations**.
2. From the three-dot menu, select **Custom repositories**.
3. Add:

   ```text
   https://github.com/Mqbretrofit/ha-anthbot-map-v2
   ```

4. Select category **Integration**.
5. Select **Add**.

### 2. Install the integration

1. Find **Anthbot Map** in HACS.
2. Install the latest stable version.
3. Restart Home Assistant.

The `anthbot-map-card` is bundled with the integration and is updated with it. A separate HACS dashboard repository is not required.

### 3. Add the ANTHBOT account

1. Open **Settings -> Devices & services**.
2. Select **Add integration**.
3. Search for **Anthbot Map**.
4. Enter the ANTHBOT account details.
5. Wait for Home Assistant to create the mower device and entities.

## Lovelace resource

In Lovelace storage mode, the integration automatically creates or updates:

```text
/anthbot-map-v2/anthbot-map-card.js
```

Resource type: **JavaScript module**. No manual setup is normally required.

### If the resource was not created automatically

1. Open **Settings -> Dashboards -> Resources**.
2. Add:

   ```text
   /anthbot-map-v2/anthbot-map-card.js?v=2.4.6.4
   ```

3. Select type **JavaScript module**.
4. Restart Home Assistant and hard-refresh with `Ctrl+Shift+R`.

Only one Anthbot Map Card resource should be enabled at a time.

## Manual installation

1. Download the ZIP file from the [latest GitHub release](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/latest).
2. Copy `custom_components/anthbot_map/` to `/config/custom_components/anthbot_map/`.
3. Restart Home Assistant.
4. Open **Settings -> Devices & services** and add **Anthbot Map**.

# Adding the map card

## Minimal configuration

Find the map entity under **Developer Tools -> States**. Its entity ID normally ends with `_map`.

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
```

Replace `sensor.YOUR_MOWER_map` with the actual map entity ID.

## Using a garden photograph

Copy a top-down image to `/config/www/garden.jpg` and reference it as:

```yaml
image: /local/garden.jpg
```

A top-down aerial or drone photograph with minimal perspective distortion gives the best calibration result.

## Recommended full configuration

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
image: /local/garden.jpg
height: 720
fit: cover
refresh_interval: 3
robot_heading_source: cloud
robot_heading_offset: 0
mowed_path_color: rgba(255, 235, 59, 0.82)
mowed_path_width: 10
boundary_width: 3
boundary_color: rgba(74, 101, 255, 0.9)
show_zones: true
show_no_go_zones: true
show_no_go_labels: true
show_mowed_path: true
show_decoded_boundary: true
calibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
robotCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
mowingPathCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
decodedBoundaryCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Default menu layout

The card can start on a selected main panel, with the floating menu already open and with a selected submenu expanded.

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
default_panel: settings
menu_open: true
default_submenu: edgeSettings
```

Supported `default_panel` values are `control`, `settings`, `interface`, `status`, `maintenance` and `diagnostics`.

Useful `default_submenu` values include `global`, `custom-button-actions`, `edgeSettings`, `manual`, `auto`, `zone-set` and `auto-zone-set`. A specific zone submenu can also be selected with a generated key such as `manual-3` or `auto-2`.

# Calibration

The four calibration sections control different map layers.

## Map alignment

`calibration` performs the base alignment of the complete ANTHBOT map coordinate system to the garden photograph. Use it first.

```yaml
calibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Mower calibration

`robotCalibration` fine-tunes the mower icon position, size and direction correction. It does not rotate the mowing path.

```yaml
robotCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Mowing-path calibration

`mowingPathCalibration` independently moves, scales and rotates the current mowing path, historical paths and mowing-coverage rendering.

```yaml
mowingPathCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Boundary calibration

`decodedBoundaryCalibration` separately aligns the decoded lawn boundary.

```yaml
decodedBoundaryCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Recommended calibration order

1. Use **Map alignment** to align the complete map with the photograph.
2. Use **Mowing-path calibration** to align the path and coverage.
3. Use **Mower calibration** to fine-tune the mower icon and its direction.
4. Use **Boundary alignment** to align the decoded boundary.
5. Select **Copy YAML** and save the generated configuration.

`offsetX`, `offsetY`, `scaleX` and `scaleY` are relative values. `rotation` values in calibration blocks are radians.

# Mower heading

Recommended setting:

```yaml
robot_heading_source: cloud
```

Available modes:

- `cloud`: official-app-compatible cloud `pose.yaw`; recommended;
- `movement`: calculate heading from consecutive positions;
- `auto`: prefer movement and fall back to the cloud heading.

The official application treats `pose.yaw` as milliradians. The card uses:

```text
degrees = yaw * 180 / (pi * 1000)
```

For a fixed image-alignment difference, use:

```yaml
robot_heading_offset: 0
robot_image_rotation: 90
```

These two values are degrees.

# Mowing history

1. Open the **Anthbot Map** card.
2. Open the floating menu in the lower-right corner.
3. Select **Diagnostics**.
4. Expand **Previous mowing tasks**.
5. Select a completed session.

History entries can show the date, duration, mowed area, progress, mowing mode, start reason, affected zones and available historical area/map/path data.

The list is refreshed from the ANTHBOT cloud periodically. Visual detail opens only when the cloud record contains an area, map or path file; the summary remains visible when no visual file is available.

# Language

The card follows the Home Assistant interface language by default:

```yaml
language: auto
```

Supported languages are English, Hungarian, German, French, Spanish, Italian, Portuguese, Dutch, Polish, Czech, Slovak, Romanian, Danish, Swedish, Norwegian, Finnish, simplified Chinese, traditional Chinese, Turkish, Thai, Vietnamese, Korean and Khmer. Unsupported languages fall back to English.

# Updating

When using HACS:

1. Install the update offered by HACS.
2. Restart Home Assistant.
3. Hard-refresh the browser with `Ctrl+Shift+R` if the frontend still looks old.

In Lovelace storage mode, the integration updates the resource version automatically. In YAML resource mode, update the cache-busting query after an upgrade, for example:

```text
/anthbot-map-v2/anthbot-map-card.js?v=2.4.6.4
```

# Troubleshooting

## Card not found

Check that:

- Anthbot Map is installed and Home Assistant has been restarted;
- `/config/www/anthbot-map-v2/anthbot-map-card.js` exists;
- `/anthbot-map-v2/anthbot-map-card.js` is listed as a JavaScript module;
- no duplicate old Anthbot Map Card resource is enabled.

Then hard-refresh with `Ctrl+Shift+R`.

## Map is not displayed

Check that the correct map entity is configured, its state is `ready`, and its attributes contain the expected map/pose data for the mower model. Also check the Home Assistant log for `anthbot_map` errors.

M-series map handling is supported and has been directly tested on M9 Pro hardware. N8 map/path support is currently a model-specific testing path and still needs real-device verification.

## Mower heading is incorrect

Start with `robot_heading_source: cloud`. If the icon has a constant angular offset, adjust `robot_heading_offset`, then fine-tune **Mower calibration**.

## Mowing history is missing

Check that the card uses the correct mower's map entity, `mowing_records` is present in its attributes, the cloud connection works and the corresponding cloud record actually contains history data.

## Repeated old diagnostic/error report

Version 2.4.6.4 adds episode-based deduplication and stale task-event handling. After updating, restart Home Assistant once so the current condition becomes the startup baseline.

## Live map/position stopped after an MQTT error

Version 2.4.6.4 keeps the live-shadow supervisor running after normal transport/runtime failures and rotates temporary IoT credentials after repeated reconnect failures. Check the `anthbot_map` logs and Developer Agent diagnostics before changing model-specific code.

# Reporting problems

Open an issue at:

https://github.com/Mqbretrofit/ha-anthbot-map-v2/issues

If you attach diagnostics manually, remove passwords, bearer tokens, AWS IDs/keys, mower serial numbers, PIN codes, GPS coordinates, garden photographs and other personal data. Built-in project diagnostics apply their own filtering, but you should still review anything you publish publicly.

# Credits

- https://github.com/vincentjanv/anthbot_genie_ha
- https://github.com/AdrianTIonut/anthbot_genie_ha
- https://github.com/reloxx13/ioBroker.anthbot-genie

# License

MIT - see [LICENSE](LICENSE).
