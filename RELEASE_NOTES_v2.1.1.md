# Anthbot Map v2.1.1

This stable release promotes the field-tested `2.2.1-beta.48` feature set. It
contains the following changes compared with stable `2.0.0`.

## v2.1.1 edge-settings fixes

- Fixed the initial values in the edge editor: the card now prefers the
  current, app-compatible separate `ridable_area` definition instead of an
  older copy embedded in the general area definition.
- After a successful save, the new cutting height and boundary-overlap values
  are published to Home Assistant immediately, so reopening the editor no
  longer shows cached values for up to five minutes.
- The same source-priority fix is included in both the Anthbot Map Card and the
  Garden Map Card v163.
- Empty technical edge records without usable vertices remain hidden.
- The complete edge list is still sent to the mower, preserving every
  untouched edge.

## App-style mowing task control

- Added a single app-style task selector for full-area mowing, manual zones,
  automatic zones, outer-edge mowing and dock-surroundings mowing.
- Manual and automatic zones are shown only when the mower exposes them.
- Added multi-zone selection and an explicit mowing order.
- One, two or all available zones can be selected without losing the selection.
- Added optional edge cutting for each selected zone.
- Selected targets use a full colored state instead of a small check mark.
- The main action is now one dynamic control: Start, Pause and Resume.
- Pause keeps the current task; Resume restarts the exact saved full-area,
  manual-zone, automatic-zone, edge or dock-surroundings task.
- The resumable task is persisted across Home Assistant restarts.
- Stop clears the saved task and prevents an invalid resume attempt.
- Added a translated message when there is no task to resume.
- Restored the proven command route used by beta.35 for concrete zone buttons.
- Improved command feedback for sent, cloud-accepted, robot-confirmed, rejected
  and unconfirmed operations.
- Removed duplicate legacy zone/start/stop/dock controls from secondary views.
- Made mouse and touch controls react reliably to a single press.

## Global mower settings

- Added mowing-pass count.
- Added edge-following return.
- Added automatic dock-area mowing.
- Added visual obstacle detection on/off control.
- Added Low, Medium and High visual obstacle sensitivity.
- Combined visual obstacle detection and sensitivity into one compact setting.

## Manual and automatic zone settings

- Added separate settings for manual and automatic zones.
- Added per-zone mowing-pass count and cutting height.
- Added per-zone visual obstacle detection and sensitivity.
- Added per-zone custom mowing direction on/off control and direction angle.
- Added per-zone edge-cutting control.
- Settings are written using the app-compatible complete `area_set` payload so
  changing one zone preserves every other zone.
- Zone panels are collapsible and keep their independently opened/closed state
  during live refreshes and selection changes.
- Fixed manual and automatic zone entity identification and names.
- Fixed selection of three or more zones and preserved the selected order.
- Removed click propagation and gray hover flicker from zone controls.
- Live updates are temporarily frozen while a setting is actively edited, so
  sliders, toggles and open panels no longer jump back to the top.

## Editable boundary and edge overlap

- Added download and parsing of the app's separate `ridable_area` map file.
- Added the app-compatible `set_edge_settings` Home Assistant service.
- Added cutting-height selection for each editable boundary edge.
- Added boundary-overlap values of 5, 7, 10, 13, 15, 17 and 20 cm.
- The full `ridable_area_set` list is sent so untouched edges are preserved.
- Added an app-style visual overlap editor with the ANTHBOT mower image.
- The mower and measurement arrow move together: the selected distance is
  measured from the boundary to the mower edge.
- Empty or deleted edge definitions without vertices are hidden.
- Added `ridable_area_error` diagnostics.
- Large edge definitions and diagnostics are excluded from Recorder history.

## Maintenance, records and diagnostics

- Added a separate Maintenance menu.
- Added the remaining blade, camera-cleaning and charging-contact life values.
- Added reset services for blade replacement, camera cleaning and charging-
  contact cleaning.
- Corrected the blade, camera and charging-contact value mapping so Maintenance
  and Diagnostics show the same components and percentages.
- Added previous mowing-task records from the mobile-app API.
- Added detailed local error-code history.
- Added cloud, robot-online and live MQTT state to diagnostics.

## MQTT and cloud connection stability

- Aligned MQTT-over-WebSocket setup with the ANTHBOT Android 2.15.15 app.
- Uses the app's `mqttv3.1` WebSocket subprotocol and `okhttp/4.12.0` identity.
- Uses the AWS IoT Device SDK JavaScript 2.2.15 CONNECT identity, a fresh UUID
  client ID and the app's 300-second keepalive.
- Corrected SigV4 WebSocket query construction and removed the non-app
  `X-Amz-Expires` parameter.
- Sends the already signed query byte-for-byte without URL recanonicalization.
- Keeps app-issued temporary AWS credentials until their actual expiry instead
  of rotating them repeatedly after transient 403/404 responses.
- Normalizes duration-style credential expiry values correctly.
- Added persistent reconnect with bounded exponential delay.
- Subscribes only to the named-shadow response topics used by the app and
  accepted by the mower's IoT policy.
- Verifies MQTT CONNACK and SUBACK before reporting the connection as online.
- Handles multiple MQTT packets delivered in a single WebSocket frame.
- Commands use the active MQTT service-shadow connection, matching the app.
- Removed the misleading HTTP command fallback that the cloud could accept
  without the mower executing the command.
- Added safe handshake diagnostics containing only approved AWS error headers.

## Card and mobile interface

- Added the proven Garden Map Card mobile layout.
- The map fills the available phone or tablet viewport.
- Added `mobile_map_rotation`, `mobile_map_fit` and `mobile_robot_size` options.
- Corrected `contain` geometry at +90 and -90 degree rotations.
- Added compact two-column mobile controls and a 76% scrollable glass panel.
- Improved touch-device detection and fixed fixed-height mobile cards.
- Prevented live mower refreshes from replacing a control between pointer-down
  and click.
- Kept the integration frontend and `/www/anthbot-map` copy byte-identical.

## Localization

- Added all new controls, settings, feedback, maintenance, history and edge-
  editor text to all 23 supported languages.
- Corrected Hungarian labels and completed manual/automatic zone translations.

## Validation

- 70 automated Python regression tests pass.
- All bundled JavaScript files pass syntax validation.
- The Home Assistant frontend copies are verified byte-for-byte.
- The manifest, Recorder exclusions and complete release archive are validated
  by the GitHub workflow.
