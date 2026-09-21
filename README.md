# Anthbot Map for Home Assistant

[English](README.md) | [Magyar](README_HU.md)

[![Release](https://img.shields.io/badge/release-v2.4.9.1-blue)](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.9.1)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mqbretrofit&repository=ha-anthbot-map-v2&category=integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-EA4AAA?logo=githubsponsors)](https://github.com/sponsors/Mqbretrofit)

Unofficial Home Assistant integration and custom map card for ANTHBOT robotic lawn mowers.

Anthbot Map connects Home Assistant to the ANTHBOT cloud, creates model-aware mower entities, and bundles the `anthbot-map-card` Lovelace card. It provides mower control, map/path/zone rendering, mowing history, diagnostics, Battery Saver functions, and model-specific handling for Genie, M-series, N8, and Pion/MGC devices.

> [!WARNING]
> This is an independent community project and is not affiliated with or endorsed by ANTHBOT.

## ❤️ Support development

Anthbot Map is an independent open-source community project. Continued development includes protocol research, model-specific implementation, map/path decoding, diagnostics, regression testing and real-device validation.

If this integration is useful to you, you can support continued development through **[GitHub Sponsors](https://github.com/sponsors/Mqbretrofit)**. For sponsored feature requests, priority development and additional support options, see **[SUPPORT.md](SUPPORT.md)**.

## Current version

Stable version: **2.4.9.1**

Latest release: [Anthbot Map v2.4.9.1](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.9.1)

### Highlights in 2.4.9.1

- Fixes the Home Assistant thread-safety RuntimeError from the `Next mow` sensor's periodic refresh.
- Keeps the one-minute `Next mow` refresh, but executes it safely on the Home Assistant event loop.
- Stops the Voice Pack select from overflowing Recorder's 16 KiB attribute limit by excluding its large live diagnostics from database history; the live UI still receives them.

### Highlights in 2.4.9.0

- Adds **voice-pack management for speech-capable ANTHBOT Genie models** and the ANTHBOT Community Voice Store. M9/M9 Pro do not support spoken voice packs; their existing volume control remains available.
- Adds Stripe-backed paid voice purchases with automatic entitlement recognition and unlock refresh without manually reloading the Anthbot Map page.
- Installs purchased community voices on compatible **Genie** mowers through the ANTHBOT voice OTA path with status and verification feedback.
- Adds a native Home Assistant **Firmware Update** entity using ANTHBOT vendor metadata, presigned package URLs, MD5 validation, manual installation and progress reporting.
- Keeps unverified automatic firmware-update writes disabled.
- Moves project-controlled voice-store, diagnostics and developer API traffic to `anthbotmap.com`.
- Real-device validation completed on **Genie 1000** for the full Voice Store → Stripe payment → automatic unlock → purchased voice installation flow.

### Highlights in 2.4.8.2

- Adds a dedicated **Pion / MGC** model family for identifiers such as `MGC500`, `MGC750` and `MGC1000`; these devices no longer fall through to Genie-only handling.
- Fixes the native MGC schedule format: scalar `week: 1..7` values are handled as individual weekdays and MGC keeps its one-appointment-per-day/full-lawn shape.
- Uses the native Pion/MGC start path without the Genie-only `app_state` preamble.
- Exposes confirmed MGC cutting height, mowing progress/area, rain state, Wi-Fi/IP, path payload and firmware data through an isolated Pion normalization layer.
- Leaves unverified Pion/MGC setting writes and `curpath` decoding disabled rather than sending guessed commands.

### Highlights in 2.4.8.1

- Fixes native ANTHBOT app schedule write-back for M5/M9/N8/Pion-family mowers.
- Uses the exact M-series `appointment` / `delete_appointment` payload and generates the required next numeric rule ID.
- Keeps the working Genie schedule path unchanged.
- Creating an M9 Pro schedule from the card was verified on real hardware: the rule now appears in the ANTHBOT app.
- Full release validation passed **365/365 unit tests**.

### Highlights in 2.4.8.0

- Uses the mower's native ANTHBOT app schedule as the single source of truth and mirrors it into the HA calendar and Anthbot Map Card.
- Creates, edits and deletes native weekly app rules from the card while preserving model- and firmware-specific fields.
- Adds timed **mow until** and **remain parked until** overrides with a clear action.
- Adds per-mower `next_mow`, native HA mower/schedule events, optional weather blocking and bounded catch-up.
- Supports zones and cutting height per weekly rule; disabled app rules remain visible but do not create a next-mow time.
- Shows the real next mow in blue in the floating map status display only when one exists.
- Genie 1000 native app schedule loading was verified on real hardware; full release validation passed **363/363 unit tests**.

### Highlights in 2.4.7.3

- Improves live-map performance by coalescing bursty coordinator updates before WebSocket publication.
- Moves live-map snapshot and delta construction out of the Home Assistant event loop and freezes mutable path data before frame construction, preventing torn updates while a trajectory is still growing.
- Preserves reconnect/full-snapshot continuity, sequence/resync protection, rolling-window behavior, and absolute-index live-path handling.
- Includes the latest Genie live-path and mowing-progress presentation hardening, M-series progress post-trim handling, stationary-position handling, and location-recorder hardening from the tested 2.4.7.2 performance line.
- Preserves the startup-safe Developer Agent lifecycle and cloud/API resilience fixes introduced in 2.4.7.2.
- Keeps production mower command routing unchanged, including the verified M-series `stop_all_tasks` payload; only stale regression expectations were updated.
- Full pre-release validation completed successfully: **359/359 unit tests passed**, plus Python compilation and targeted live-map checks.
- Repository release documentation is consolidated in `CHANGELOG.md`; GitHub Releases retain the published historical release notes.

### Highlights in 2.4.7.0

- High-frequency live map/path/pose data is separated from the Home Assistant entity state machine and delivered to the card through a dedicated WebSocket transport.
- The card receives a full snapshot when it connects, then incremental path deltas with sequence tracking, automatic resync, path-id reset handling, and rolling-window support.
- In live-stream mode the Map entity stays compact: the full `path`, `cloud_path`, `mowed_path`, and `pose` geometry is not stored in Home Assistant state or Recorder.
- Legacy periodic Map-entity polling is disabled while the live stream is active, reducing Recorder churn to roughly a one-minute heartbeat when no relevant compact state changes occur.
- Expensive No-Go geometry evaluation is moved off the Home Assistant event loop for M-series, N8, and Genie path diagnostics, with stable revision caching and bounded live evaluation cadence.
- Mower command routing is unchanged; Genie, M5/M9-family, and N8 control paths remain separated.
- Real-device validation on an ANTHBOT M9 Pro confirmed live WebSocket path updates, Recorder reduction, Home Assistant restart, reconnect, and full snapshot restore.

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

N8-specific control, status, map/path handling, and model-scoped entities are included.

- **Code/API validation:** completed with dedicated regression and model-isolation tests.
- **2.4.7.3 stability coverage:** N8 uses the protected No-Go executor path and dedicated regression tests, while the current live-map transport preserves the same model isolation.
- **Real N8 hardware validation:** not yet completed directly by this project.
- Existing Genie and M-series model routing remains separated from N8 routing.

N8 owners are welcome to test and report model-specific behavior.

## Supported models

- **ANTHBOT Genie:** supported and directly hardware-tested; Genie-specific path diagnostics remain separated from other models.
- **ANTHBOT M9 Pro:** M-series control, status, map, path, zone, and history handling supported and directly hardware-tested, including the 2.4.7.3 live-stream/Recorder architecture and follow-up performance hardening.
- **ANTHBOT M9:** supported through the shared M-series implementation; not directly hardware-tested by this project yet.
- **ANTHBOT M5:** supported through the shared M-series implementation; not directly hardware-tested by this project yet.
- **ANTHBOT N8:** dedicated N8 implementation included; code/API and regression validated, but direct 2.4.7.3 hardware validation is still pending.
- **ANTHBOT Pion / MGC500 / MGC750 / MGC1000:** isolated model detection, flat-shadow status normalization, native schedule parsing/write shape and native start routing are included. Map/path decoding and unverified setting writes remain intentionally disabled until protocol/hardware confirmation.

## Features

- ANTHBOT cloud login from the Home Assistant UI
- multiple mowers on one ANTHBOT account
- persistent AWS IoT/MQTT live-shadow updates with reconnect supervision
- dedicated WebSocket live-map transport with snapshot, delta, sequence and automatic resync handling
- compact Map entity design that keeps high-frequency live geometry out of Home Assistant state/Recorder while live-stream mode is active
- native Home Assistant `lawn_mower` entity
- native ANTHBOT app schedule mirrored to the HA calendar and card, with write-back editing
- timed mow/park overrides and a per-mower next-effective-mow sensor
- per-rule zones, cutting height and optional weather forecast/catch-up behavior
- native mower lifecycle and schedule events for HA automations
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

Schedule setup and examples: [Home Assistant scheduling and overrides](docs/HA_SCHEDULING.md).

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
/anthbot-map-v2/anthbot-map-card.js?v=2.4.9.0
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
/anthbot-map-v2/anthbot-map-card.js?v=2.4.9.0
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

Check that the correct mower map entity is configured and that its state is `ready`. In normal 2.4.7.3 live-stream mode, full live `path`/`pose` geometry is intentionally **not** stored in Map entity attributes. Instead, the Map entity should advertise `live_stream_available: true` and `live_stream_transport: websocket`, while the card receives the full snapshot and live deltas through Home Assistant WebSocket.

If the map still does not render, hard-refresh the browser, verify that only one Anthbot Map frontend resource is active, and check the Home Assistant log for `anthbot_map` or WebSocket errors.

## N8 issue

N8 support is included and code/API validated, but direct 2.4.7.3 hardware validation has not yet been completed by this project. Please attach privacy-cleaned diagnostics when reporting N8-specific behavior.

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
