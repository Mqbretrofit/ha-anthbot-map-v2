# Anthbot Map for Home Assistant

[English](README.md) | [Magyar](README_HU.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mqbretrofit&repository=ha-anthbot-map-v2&category=integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Unofficial Home Assistant integration and custom map card for ANTHBOT robotic
lawn mowers.

The integration connects Home Assistant to the ANTHBOT cloud, creates the
entities required to monitor and control the mower, and bundles the
`anthbot-map-card` Lovelace card.

The card can display the mower, charging station, lawn boundary, mowing zones,
no-go zones, live and historical mowing paths, covered area, and an optional
aerial or drone photograph of the garden.

> [!WARNING]
> This is a community project and is not affiliated with ANTHBOT.

## Current version

Stable version: **2.4.2**

### Highlights in 2.4.2

- Adds per-mower custom card-button actions saved in Home Assistant while
  preserving the existing YAML `button_actions` format.
- Immediately rebinds the restart-safe 55+1 minute anti-shutdown guard when
  the configured charger smart plug changes.
- Changing the battery-saver percentage thresholds does not reset timers that
  are already running.
- Invalid settings left over from previous versions are automatically corrected
  to safe values.
- Preserves all existing battery-saver profiles, translations, RTK handling,
  mower controls, and restart persistence.

### Highlights in 2.4.1

- Added three ready-made battery-care profiles: **Maximum battery care**,
  **Balanced**, and **Always ready**, plus fully adjustable custom settings.
- Battery-saver settings and operating state are persisted per mower, including
  charge limits, shared RTK power, current phase, and anti-shutdown timing.
  Home Assistant restarts no longer reset the active battery-saver cycle.
- Added the **55+1 minute anti-shutdown protection**: while the mower is docked
  in standby with charger power off, the charger is enabled for one minute
  after 55 minutes, then the cycle restarts.
- The card shows anti-shutdown status and the countdown to the next keep-awake
  pulse, including initialization and active pulse states.
- Normal maintenance charging is kept separate from the short keep-awake pulse,
  and charger power is not switched blindly while mower telemetry is unavailable.
- Shared and separate RTK power are handled correctly during mowing, return to
  dock, charging, and RTK initialization.
- Disabling Battery saver mode immediately restores charger power, while
  deliberate manual charging remains separate from automatic battery-saver
  transitions.
- Fixed integration unload/reload handling and made saved settings apply to the
  running coordinator without requiring a Home Assistant restart.
- The Battery saver tile remains a settings-dialog opener; the larger mode
  checkbox stays inside the dialog.
- The complete battery-saver interface is available in all 23 supported
  languages.

### Highlights in 2.4.0

- Added an optional battery-saving mode for chargers controlled by a Home
  Assistant switch entity.
- Added independently configurable upper charge, idle maintenance, and
  interrupted-task resume levels.
- Low-battery returns are detected from ANTHBOT cloud task event `1021`; live
  mowing progress is not exposed by the cloud API and is not estimated.
- Home Assistant-started full-map, zone, outer-edge, and dock-edge tasks can be
  remembered and resumed after recovery charging.
- Automatic charger switch-on temporarily mutes the mower and restores the
  previous volume afterwards.
- Added cloud task event sensors and task-event diagnostics.

### Highlights in 2.3.0

- Previous mowing tasks now include their available area, map, and path data.
- The map, mower icon, mowing path, and decoded boundary can be calibrated
  separately.
- Mirrored mower heading during horizontal travel has been corrected.
- Mowing-path rotation on non-square maps has been corrected.
- Accounts containing multiple mowers are handled more reliably.
- Calibration and mowing-history text is available in all 23 supported
  languages.
- Remaining frontend debug output has been removed.
- Experimental M5/M9 shadow and live-path handling has been added.

> [!IMPORTANT]
> **Map display is not yet working on ANTHBOT M5 and M9 mowers.** M5/M9
> support is experimental, and available states and features can vary by model
> and firmware version.

## Supported models

The integration is tested primarily with ANTHBOT Genie-series mowers.

- ANTHBOT Genie: primary support
- ANTHBOT M5/M9: experimental support
- M5/M9 map display: not currently working

## Using another ANTHBOT integration

Anthbot Map v2 uses its own `anthbot_map` integration domain, so it can remain
installed beside an older ANTHBOT integration. Do not enable both integrations
at the same time.

> [!CAUTION]
> Do not run Anthbot Map together with `vincentjanv/anthbot_genie_ha`, the
> AdrianTIonut fork, or another ANTHBOT Home Assistant integration. Concurrent
> integrations can open competing cloud sessions and send conflicting commands
> to the same mower.

Safe migration and rollback:

1. Leave the previous integration installed.
2. Disable its config entry under **Settings -> Devices & services**.
3. Restart Home Assistant.
4. Add and test **Anthbot Map**.
5. To roll back, disable Anthbot Map, enable the previous integration, and
   restart Home Assistant.

Existing entity-registry entries can cause the new entity IDs to receive an
`_2`, `_3`, or later suffix. This is expected and is not an error.

## Features

- ANTHBOT cloud login from the Home Assistant UI
- multiple mowers on one ANTHBOT account
- cloud polling and persistent AWS IoT/MQTT shadow updates
- automatic MQTT reconnection
- native Home Assistant `lawn_mower` entity
- full-area, manual-zone, and automatic-zone mowing
- outer-edge and dock-surroundings mowing
- pause, resume, stop, and return-to-dock commands
- battery, charging, status, RTK, network, firmware, and maintenance data
- map, zone, error, and diagnostic entities
- live mowing path and mowing-coverage display
- previous mowing tasks with area, map, and path detail
- optional aerial or drone photograph as the background
- fullscreen map, zoom, pan, and rotation
- separate map, mower, path, and boundary calibration
- generated YAML that can be copied from the card
- 23 selectable interface languages

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

The map card does not need a separate HACS dashboard repository. The
`anthbot-map-card` is bundled with the integration and is updated with it.

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
   /anthbot-map-v2/anthbot-map-card.js?v=2.4.2
   ```

3. Select type **JavaScript module**.
4. Restart Home Assistant and hard-refresh with `Ctrl+Shift+R`.

Only one Anthbot Map Card resource should be enabled at a time.

## Manual installation

1. Download the ZIP file from the latest GitHub release.
2. Copy `custom_components/anthbot_map/` to
   `/config/custom_components/anthbot_map/`.
3. Restart Home Assistant.
4. Open **Settings -> Devices & services** and add **Anthbot Map**.

# Adding the map card

## Minimal configuration

Find the map entity under **Developer Tools -> States**. Its entity ID normally
ends with `_map`.

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

A top-down aerial or drone photograph with minimal perspective distortion gives
the best calibration result.

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

The card can start on a selected main panel, with the floating menu already open,
and with a selected submenu expanded. These options are optional; when omitted,
the existing behaviour remains unchanged.

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
default_panel: settings
menu_open: true
default_submenu: edgeSettings
```

Supported `default_panel` values are `control`, `settings`, `interface`,
`status`, `maintenance`, and `diagnostics`.

Useful `default_submenu` values include `global`, `custom-button-actions`,
`edgeSettings`, `manual`, `auto`, `zone-set`, and `auto-zone-set`.
A specific zone submenu can also be selected with its generated key, for example
`manual-3` or `auto-2`. YAML defaults take precedence over the previously
remembered browser submenu only when `default_submenu` is configured.

# Calibration

The four calibration sections control different map layers.

## Map alignment

`calibration` performs the base alignment of the complete ANTHBOT map
coordinate system to the garden photograph. Use it first.

```yaml
calibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Mower calibration

`robotCalibration` fine-tunes the mower icon's position, size, and direction
correction. It does not rotate the mowing path.

```yaml
robotCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Mowing-path calibration

`mowingPathCalibration` independently moves, scales, and rotates the current
mowing path, historical paths, and mowing-coverage rendering.

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

`offsetX`, `offsetY`, `scaleX`, and `scaleY` are relative values. `rotation`
values in calibration blocks are radians.

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

History entries can show the date, duration, mowed area, progress, mowing mode,
start reason, affected zones, and available historical area, map, and path.

The list is refreshed from the ANTHBOT cloud approximately every five minutes.
Visual detail opens only when the cloud record contains an area, map, or path
file. The summary remains visible when no visual file is available.

# Language

The card follows the Home Assistant interface language by default:

```yaml
language: auto
```

Supported languages are English, Hungarian, German, French, Spanish, Italian,
Portuguese, Dutch, Polish, Czech, Slovak, Romanian, Danish, Swedish, Norwegian,
Finnish, simplified Chinese, traditional Chinese, Turkish, Thai, Vietnamese,
Korean, and Khmer. Unsupported languages fall back to English.

# Updating

When using HACS:

1. Install the update offered by HACS.
2. Restart Home Assistant.
3. Hard-refresh the browser with `Ctrl+Shift+R`.

In Lovelace storage mode, the integration updates the resource version
automatically. In YAML resource mode, update the cache-busting query after an
upgrade, for example `/anthbot-map-v2/anthbot-map-card.js?v=2.4.2`.

# Troubleshooting

## Card not found

Check that:

- Anthbot Map is installed and Home Assistant has been restarted;
- `/config/www/anthbot-map-v2/anthbot-map-card.js` exists;
- `/anthbot-map-v2/anthbot-map-card.js` is listed as a JavaScript module;
- no duplicate old Anthbot Map Card resource is enabled.

Then hard-refresh with `Ctrl+Shift+R`.

## Map is not displayed

Check that the correct map entity is configured, its state is `ready`, and its
attributes contain `pose` and map data. Also check the Home Assistant log for
`anthbot_map` errors.

Map display on M5/M9 is a known limitation and is not currently working.

## Mower heading is incorrect

Start with `robot_heading_source: cloud`. If the icon has a constant angular
offset, adjust `robot_heading_offset`, then fine-tune **Mower calibration**.

## Mowing history is missing

Check that version 2.3.0 or newer is installed, the card uses the correct
mower's map entity, `mowing_records` is present in its attributes, the cloud
connection works, and at least five minutes have passed since the last refresh.

# Reporting problems

Open an issue at:

https://github.com/Mqbretrofit/ha-anthbot-map-v2/issues

Before publishing diagnostics, remove passwords, bearer tokens, AWS IDs and
keys, mower serial numbers, PIN codes, GPS coordinates, garden photographs,
and other personal data.

# Credits

- https://github.com/vincentjanv/anthbot_genie_ha
- https://github.com/AdrianTIonut/anthbot_genie_ha
- https://github.com/reloxx13/ioBroker.anthbot-genie

# License

MIT - see [LICENSE](LICENSE).
