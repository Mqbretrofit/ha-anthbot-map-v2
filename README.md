# Anthbot Map for Home Assistant

[English](README.md) | [Magyar](README_HU.md)

[![Release](https://img.shields.io/badge/release-v2.4.6.4-blue)](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.6.4)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mqbretrofit&repository=ha-anthbot-map-v2&category=integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-EA4AAA?logo=githubsponsors)](https://github.com/sponsors/Mqbretrofit)

Unofficial Home Assistant integration and custom map card for ANTHBOT robotic lawn mowers.

Anthbot Map connects Home Assistant to the ANTHBOT cloud, creates model-aware mower entities, and bundles the `anthbot-map-card` Lovelace card. It provides mower control, map/path/zone rendering, mowing history, diagnostics, Battery Saver functions, and model-specific handling for Genie, M-series, and N8 devices.

> [!WARNING]
> This is an independent community project and is not affiliated with or endorsed by ANTHBOT.

## ❤️ Support development

Anthbot Map is an independent open-source community project. Continued development includes protocol research, model-specific implementation, map/path decoding, diagnostics, regression testing and real-device validation.

If this integration is useful to you, you can support continued development through **[GitHub Sponsors](https://github.com/sponsors/Mqbretrofit)**. For sponsored feature requests, priority development and additional support options, see **[SUPPORT.md](SUPPORT.md)**.

## Current version

Stable version: **2.4.6.4**

Latest release: [Anthbot Map v2.4.6.4](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.6.4)

### Highlights in 2.4.6.4

- Automatic diagnostics are episode/edge triggered, so an unchanged persistent diagnostic condition is not repeatedly reported every hour.
- Existing diagnostic conditions are seeded on startup, preventing an old condition from being replayed only because Home Assistant or the integration restarted.
- Historical cloud task-event errors keep their history but now carry freshness/stale metadata and do not independently trigger automatic error reporting after they expire.
- AWS IoT live-shadow supervision survives unexpected runtime/transport failures instead of allowing the background listener to die permanently.
- After repeated reconnect failures, temporary IoT credentials can be rotated and bounded reconnect attempts continue.
- M-series map identity handling now keeps logical `map.map_id`, `area_id`, `plan_id`, and the raster map id from `map_manager_<serial>.tar.gz` separate.
- Different logical and raster map IDs no longer cause unnecessary M-series map-manager downloads.
- The M-series map fix stays scoped to M5/M9-family models and does not widen or change N8 command routing.

### 2.4.6.x reporting and developer diagnostics

The 2.4.6 series also added and refined optional project diagnostics:

- opt-in anonymous usage statistics for installation/model/version visibility;
- opt-in automatic diagnostic reports for newly active mower and cloud task-event errors;
- a lightweight version heartbeat when anonymous statistics are enabled;
- a separate **Allow read-only developer requests** permission in **Anthbot Map -> Settings -> Development and diagnostics**;
- opt-in read-only Developer Agent tools including `full_state`, `full_diagnostics`, `state_inspector`, `state_diff`, and `refresh_diagnostics`;
- strict read-only behavior: no arbitrary Python, URL, HTTP, MQTT, method/property execution, or mower-control commands are exposed through Developer Agent requests.

Anonymous statistics, automatic diagnostics, and read-only developer access are separate permissions. They are not required for normal mower operation.

### N8 support

N8-specific control, status, map/path handling, and model-scoped entities are included and available for testing.

- **Code/API validation:** completed with dedicated regression and model-isolation tests.
- **Real N8 hardware validation:** not yet completed by this project.
- Existing Genie and M-series model routing remains separated from N8 routing.

N8 owners are welcome to test and report model-specific behavior.

## Supported models

- **ANTHBOT Genie:** supported and directly hardware-tested.
- **ANTHBOT M9 Pro:** M-series control, status, map, path, zone, and history handling supported and directly hardware-tested.
- **ANTHBOT M9:** supported through the shared M-series implementation; not directly hardware-tested by this project yet.
- **ANTHBOT M5:** supported through the shared M-series implementation; not directly hardware-tested by this project yet.
- **ANTHBOT N8:** implementation included and available for testing; code/API validated, but real N8 hardware validation is still pending.

## Features

- ANTHBOT cloud login from the Home Assistant UI
- multiple mowers on one ANTHBOT account
- persistent AWS IoT/MQTT live-shadow updates with reconnect supervision
- native Home Assistant `lawn_mower` entity
- full-area, zone, outer-edge, and dock-surroundings mowing controls where supported
- pause, resume, stop, and return-to-dock commands
- model-specific Genie / M-series / N8 routing
- battery, charging, status, RTK, network, firmware, maintenance, error, and diagnostic data
- map, lawn boundary, zones, no-go zones, mower position, live path, and mowing coverage
- previous mowing tasks with available area, map, path, duration, and zone information
- optional aerial/drone photograph background
- fullscreen map, zoom, pan, and rotation
- separate map, mower, mowing-path, and decoded-boundary calibration
- model-specific mower images
- per-mower custom card-button actions
- Battery Saver profiles, charge thresholds, shared/separate RTK power handling, and restart-persistent state
- recurring 55+1 minute Shutdown Guard for supported smart-plug charger setups
- rain-hold handling and task-event diagnostics
- optional anonymous usage statistics, automatic diagnostics, and read-only Developer Agent access
- 23 selectable interface languages

## Using another ANTHBOT integration

Anthbot Map v2 uses its own `anthbot_map` integration domain, so it can remain installed beside an older ANTHBOT integration. Do not enable two mower integrations for the same robot at the same time.

> [!CAUTION]
> Do not run Anthbot Map together with `vincentjanv/anthbot_genie_ha`, the AdrianTIonut fork, or another ANTHBOT Home Assistant integration against the same mower. Concurrent integrations can open competing cloud sessions and send conflicting commands.

Safe migration and rollback:

1. Leave the previous integration installed.
2. Disable its config entry under **Settings -> Devices & services**.
3. Restart Home Assistant.
4. Add and test **Anthbot Map**.
5. To roll back, disable Anthbot Map, enable the previous integration, and restart Home Assistant.

Existing entity-registry entries can cause new entity IDs to receive `_2`, `_3`, or later suffixes. This is expected and is not an error.

## Requirements

- Home Assistant 2024.1.0 or newer
- HACS for the recommended installation method
- a working ANTHBOT account
- internet access to the ANTHBOT cloud

# Installation

## Install with HACS

1. Open **HACS -> Integrations**.
2. Open the three-dot menu and select **Custom repositories**.
3. Add:

   ```text
   https://github.com/Mqbretrofit/ha-anthbot-map-v2
   ```

4. Select category **Integration**.
5. Install **Anthbot Map**.
6. Restart Home Assistant.
7. Open **Settings -> Devices & services -> Add integration** and search for **Anthbot Map**.

The `anthbot-map-card` is bundled with the integration and does not need a separate HACS dashboard repository.

## Manual installation

1. Download the ZIP from the latest GitHub release.
2. Copy `custom_components/anthbot_map/` to `/config/custom_components/anthbot_map/`.
3. Restart Home Assistant.
4. Add **Anthbot Map** under **Settings -> Devices & services**.

## Lovelace resource

In Lovelace storage mode the integration automatically creates or updates:

```text
/anthbot-map-v2/anthbot-map-card.js
```

Resource type: **JavaScript module**.

If it must be added manually, use:

```text
/anthbot-map-v2/anthbot-map-card.js?v=2.4.6.4
```

Only one Anthbot Map Card resource should be enabled at a time.

# Adding the map card

## Minimal configuration

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
```

Replace `sensor.YOUR_MOWER_map` with the actual map entity created by the integration.

## Optional garden photograph

Copy a top-down image to `/config/www/garden.jpg` and reference it with:

```yaml
image: /local/garden.jpg
```

A top-down aerial or drone photograph with minimal perspective distortion gives the best calibration result.

## Recommended calibration blocks

```yaml
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

Recommended order: base map alignment, mowing-path alignment, mower calibration, then decoded-boundary alignment.

## Mower heading

Recommended setting:

```yaml
robot_heading_source: cloud
```

Available modes:

- `cloud`: official-app-compatible cloud `pose.yaw`; recommended
- `movement`: calculate heading from consecutive positions
- `auto`: prefer movement and fall back to cloud heading

# Battery Saver

Battery Saver can use a Home Assistant switch entity to control charger power. Depending on the selected profile/settings it can manage upper charge level, idle maintenance charging, interrupted-task resume thresholds, shared/separate RTK power, and the recurring 55+1 minute Shutdown Guard.

Battery Saver state is persisted per mower so Home Assistant restarts do not reset an active battery-management cycle.

> [!IMPORTANT]
> Charger power automation requires a correctly configured Home Assistant switch entity. Verify the setup carefully before relying on automated charger power control.

# Development and diagnostics

Open **Anthbot Map -> Settings -> Development and diagnostics** to manage the optional project-reporting permissions.

The available permissions are independent:

- **Share anonymous usage statistics**
- **Automatic diagnostics**
- **Allow read-only developer requests**

Normal mower control does not require any of them.

The reporting features are designed to help diagnose real-world model/API behavior while keeping mower-control paths separate from reporting. Read-only Developer Agent requests remain restricted to built-in safe probes.

# Mowing history

Open the Anthbot Map card, choose **Diagnostics**, then **Previous mowing tasks**. Completed sessions can show date, duration, mowed area, progress, mowing mode, start reason, affected zones, and available historical map/path data.

# Updating

When using HACS:

1. Install the update offered by HACS.
2. Restart Home Assistant.
3. Hard-refresh the browser with `Ctrl+Shift+R`.

In YAML resource mode, update the cache-busting query to the installed version, for example:

```text
/anthbot-map-v2/anthbot-map-card.js?v=2.4.6.4
```

# Troubleshooting

## Card not found

Check that:

- Anthbot Map is installed and Home Assistant has been restarted;
- `/config/www/anthbot-map-v2/anthbot-map-card.js` exists;
- `/anthbot-map-v2/anthbot-map-card.js` is registered as a JavaScript module;
- no duplicate old Anthbot Map Card resource is enabled.

Then hard-refresh with `Ctrl+Shift+R`.

## Map is not displayed

Check that the correct mower map entity is configured, that its state is ready, and that the entity attributes contain current mower/map data. Also check the Home Assistant log for `anthbot_map` errors.

## N8 issue

N8 support is currently available for testing but has not yet been validated on real N8 hardware by this project. Please attach privacy-cleaned diagnostics when reporting N8-specific behavior.

# Reporting problems

Open an issue at:

https://github.com/Mqbretrofit/ha-anthbot-map-v2/issues

Before publishing diagnostics, remove passwords, bearer tokens, AWS IDs/keys, PIN codes, GPS coordinates, garden photographs, and other private information.

# Credits

- https://github.com/vincentjanv/anthbot_genie_ha
- https://github.com/AdrianTIonut/anthbot_genie_ha
- https://github.com/reloxx13/ioBroker.anthbot-genie

# Previous detailed documentation

The previous v2.4.5 README is preserved under `docs/archive/README_v2.4.5.md` for reference. Current behavior and version information should be taken from this README and the latest release notes.

# License

MIT - see [LICENSE](LICENSE).
