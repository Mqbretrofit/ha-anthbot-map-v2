# Anthbot Map for Home Assistant

[English](README.md) | [Magyar](README_HU.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Unofficial Home Assistant integration and photo-backed map card for Anthbot
Genie robotic lawn mowers.

This is a standalone integration derived from the credited MIT-licensed
projects; it is not an add-on for them. Version 2 uses its own `anthbot_map`
domain, so it can remain installed beside another Anthbot integration for
testing and quick rollback.

> [!CAUTION]
> **Do not enable this integration at the same time as
> `vincentjanv/anthbot_genie_ha`, the AdrianTIonut fork, or another Anthbot Home
> Assistant integration.** Both integrations may remain installed, but disable
> the old integration under **Settings → Devices & services** before enabling
> Anthbot Map. Running both can open competing cloud sessions and send
> conflicting commands to the same mower. During testing the new entity IDs may
> receive an `_2` suffix because the disabled integration keeps its entity
> registry entries; this makes switching back possible without reinstalling.

### Testing beside an existing Anthbot integration

1. Keep the existing integration installed and disable its config entry under
   **Settings → Devices & services**.
2. Restart Home Assistant, then add **Anthbot Map** and test it.
3. To roll back, disable Anthbot Map, enable the previous integration, and
   restart Home Assistant. Do not enable both at once.

The project combines cloud telemetry and mower control with a custom Lovelace
card that can place the live Anthbot map, zones, mowing trail, charger, and
robot on a top-down photograph of the garden.

> This project is not affiliated with Anthbot. Read [NOTICE.md](NOTICE.md)
> for attribution and trademark information.

## Features

- Anthbot cloud login from the Home Assistant UI
- support for multiple mowers on one account
- native Home Assistant `lawn_mower` entity with start, stop/pause, and dock controls
- battery, mower status, charging, RTK, network, firmware, maintenance, map,
  zone, error, and diagnostic entities
- full-lawn, manual-zone, and automatic-zone mowing controls
- pause, stop, and return-to-dock commands
- map sensor with robot position and downloadable map/path definitions
- optional aerial or drone photograph as the map background
- custom zones and no-go areas
- live and historical mowing trail
- app-style cloud history-path download and decoding
- mowing-session trail persistence across view changes and page reloads
- optional configurable mowing-coverage layer
- charger and robot icons
- full-screen view, zoom, pan, rotation, and calibration controls
- floating translucent control menu that keeps the garden map visible
- visible position and direction badges
- robot heading calculated like the official app from milliradian `pose.yaw`
- generated YAML can be copied from the card calibration panel
- automatic Home Assistant language detection and manual language selection
- 23 selectable languages, including simplified and traditional Chinese,
  Turkish, Thai, Vietnamese, Korean, and Khmer

Tested primarily with Genie-series mowers. Cloud fields and available commands
can vary by mower model and firmware.

## Repository layout

```text
custom_components/anthbot_map/   Home Assistant integration
www/anthbot-map/                        Lovelace map card
tools/anthbot_dump.py                   Optional diagnostic helper
examples/                               Example YAML
```

## Installation

### 1. Install the integration with HACS

1. Open **HACS → Integrations**.
2. Open the three-dot menu and select **Custom repositories**.
3. Add:

   ```text
   https://github.com/Mqbretrofit/ha-anthbot-map-v2
   ```

4. Select category **Integration**.
5. Install **Anthbot Map**.
6. Restart Home Assistant.
7. Open **Settings → Devices & services → Add integration**.
8. Search for **Anthbot Map** and enter the Anthbot account details.

HACS installs the integration and manages subsequent updates. The complete ZIP
on the GitHub Releases page contains the integration, map card, example files,
and documentation in one package.

### 2. Install the map card

Copy the repository folder:

```text
www/anthbot-map/
```

to:

```text
/config/www/anthbot-map/
```

The resulting main file must be:

```text
/config/www/anthbot-map/anthbot-map-card.js
```

Add the Lovelace JavaScript resource:

```text
/local/anthbot-map/anthbot-map-card.js?v=140
```

Resource type: **JavaScript module**.

The resource editor is normally available under **Settings → Dashboards →
three-dot menu → Resources**. Restart Home Assistant and hard-refresh the
browser after changing the files (`Ctrl+Shift+R`).

### Manual integration installation

Copy:

```text
custom_components/anthbot_map/
```

to:

```text
/config/custom_components/anthbot_map/
```

Then restart Home Assistant and add the integration from **Devices & services**.

## Minimal card configuration

Find the map entity in **Developer Tools → States**. Its entity ID normally
ends with `_map`.

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
image: /local/garden.jpg
height: 720
fit: cover
robot_heading_source: cloud
refresh_interval: 2
show_zones: true
show_no_go_zones: true
show_no_go_labels: true
show_mowed_path: true
show_decoded_boundary: true
```

Replace `sensor.YOUR_MOWER_map` with the actual entity ID. The background image
is optional; when used, place it in `/config/www/`, for example:

```text
/config/www/garden.jpg
```

which is referenced from Lovelace as `/local/garden.jpg`.

## Map calibration

1. Open the card and expand the map.
2. Open **Beállítások / Settings**.
3. Adjust the map, robot, and decoded boundary until they match the photograph.
4. Copy the generated YAML.
5. Replace the card configuration with the generated YAML.

Calibration values are installation-specific because every garden photograph
has a different crop, scale, and rotation.

Example generated sections:

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
  rotation: 0
decodedBoundaryCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

Rotation values in calibration blocks are radians.

## Robot direction

Use:

```yaml
robot_heading_source: cloud
```

The official application treats `pose.yaw` as milliradians. This card uses the
same conversion:

```text
degrees = yaw * 180 / (pi * 1000)
```

Available heading modes:

- `cloud` — official-app-compatible `pose.yaw`; recommended
- `movement` — calculate direction from consecutive positions
- `auto` — prefer movement and fall back to the cloud heading

If the robot image has a fixed alignment difference, use:

```yaml
robot_heading_offset: 0
robot_image_rotation: 90
```

Both values are degrees.

## Language

By default the card follows the Home Assistant user-interface language. Open
the card's **Settings** panel to select a different language. The selection is
stored in the browser and is also included in copied YAML.

```yaml
language: auto
```

Supported choices: English, Hungarian, German, French, Spanish, Italian,
Portuguese, Dutch, Polish, Czech, Slovak, Romanian, Danish, Swedish, Norwegian,
Finnish, simplified Chinese, and traditional Chinese. Unsupported languages
fall back to English.

## Updating

### Map-only mode

Use these options to display only the transparent map layer on a floorplan:

```yaml
map_only: true
transparent_background: true
```

The background image remains the calibration and aspect-ratio reference but is
not painted onto the canvas.

Both options are also available under the **Interface settings** tab and are
remembered in the current browser. Double-click or double-tap a map-only card
to restore the full interface.

The glass effect is a separate option and keeps a translucent blurred card surface:

```yaml
glass_background: true
```

`glass_background` and `transparent_background` cannot be active at the same time.

Home Assistant theme colors can be enabled separately:

```yaml
theme_background: true
```

The default is `false`, so the card keeps its own dark colors until enabled.

### Custom button actions

Commands can call a custom Home Assistant service or script:

```yaml
button_actions:
  start:
    service: script.anthbot_safe_start
  dock:
    service: script.anthbot_safe_dock
```

Supported command keys are `start`, `stop`, `dock`, `outer-edge`, `dock-edge`,
and `connect`. Buttons without an override keep their built-in action.

After updating the card files, increment the query string in the Lovelace
resource URL to avoid browser caching, for example:

```text
/local/anthbot-map/anthbot-map-card.js?v=140
```

Then restart Home Assistant and hard-refresh the browser.

## Troubleshooting

### Card is not found

- confirm the resource is a JavaScript module
- confirm `/config/www/anthbot-map/anthbot-map-card.js` exists
- open `/local/anthbot-map/anthbot-map-card.js?v=140` directly in the browser
- hard-refresh with `Ctrl+Shift+R`

### Map or robot is missing

- verify the configured map entity exists and is `ready`
- inspect its attributes for `pose`, `area_definition`, and map data
- wait for the next cloud poll
- check Home Assistant logs for `anthbot_map`

### Direction is limited to roughly -40°…+40°

An older card version is still cached. Version 79 converts milliradians
correctly. Update the resource URL and hard-refresh the browser.

### Reporting problems

Open an issue at
[github.com/Mqbretrofit/ha-anthbot-map-v2/issues](https://github.com/Mqbretrofit/ha-anthbot-map-v2/issues).

Never publish passwords, bearer tokens, AWS credentials, mower serial numbers,
PIN codes, GPS coordinates, garden photographs, or unredacted diagnostic dumps.

## Credits

- [vincentjanv/anthbot_genie_ha](https://github.com/vincentjanv/anthbot_genie_ha)
- [AdrianTIonut/anthbot_genie_ha](https://github.com/AdrianTIonut/anthbot_genie_ha)
- [reloxx13/ioBroker.anthbot-genie](https://github.com/reloxx13/ioBroker.anthbot-genie)

## License

MIT — see [LICENSE](LICENSE).
