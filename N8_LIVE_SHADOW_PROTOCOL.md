# ANTHBOT N8 / MGS03 live property-shadow evidence

Status: N8 validation notes combining ANTHBOT Android 2.15.16 static reconstruction with **shared-schema clues from an Anthbot M9 Pro capture**. The available capture is not a real N8 capture and must not be used as N8 proof.

No account credentials, serial number, location coordinates or PIN values are recorded in this document.

## Source provenance correction

The currently available live property-shadow/log probe was verified from its own device metadata as:

```text
model: Anthbot M9 Pro
system firmware: 1.0.42
```

Therefore fields observed in that probe are useful because M9 Pro and N8/MGS03 share parts of the MGS protocol family, but they remain **candidate N8 report paths** until a real N8 reports the same fields.

This distinction applies in particular to Child Lock, RTK acknowledgement fields, `voice_status`, `grass_state`, and the `device_config` grouping below.

## Child Lock candidate report field

The M9 Pro property shadow reports the physical-panel Child Lock candidate as:

```json
{
  "device_config": {
    "child_lock_switch": 0
  }
}
```

This is independent of:

```json
{
  "ui_lock": {
    "value": 0
  }
}
```

Static 2.15.16 analysis shows that `ui_lock` participates in the generic app/device command-lock guard. It must not be treated as the mower-panel Child Lock.

The isolated N8 status adapter may mirror `device_config.child_lock_switch` to `_n8_child_lock` **only when an N8 actually reports that key**. This is opportunistic read-only normalization, not a claim that the field has already been observed on N8.

No Child Lock write command is exposed. The 2.15.16 Hermes bundle contains no literal `child_lock` or `child_lock_switch` command constructor, and a generic `device_config` publisher alone is not sufficient evidence to invent the write key.

## RTK shared-schema clue

The M9 Pro capture reports:

```json
{
  "ctl_rtk_base": {
    "nrtk_base_sdk": 2,
    "rtk_base_state": 3
  }
}
```

Separately, static 2.15.16 MGS data-flow reconstruction proves the selector mapping and service command:

```text
1 = NRTK
2 = RTK
3 = Auto

ctl_rtk_base <scalar 1|2|3>
req_rtk_base_info {}
```

The N8 status adapter therefore keeps `_n8_rtk_base_state` and `_n8_nrtk_base_sdk` only if those keys are present in a real N8 state. Public Home Assistant RTK writing remains disabled until an intentional N8 mode-change capture confirms the acknowledgement path and behavior.

## Firmware warning

The observed `1.0.42` firmware belongs to the M9 Pro capture. It must **not** be used to choose the N8 DND/plan writer path.

Static 2.15.16 feature thresholds are still useful once an actual N8 firmware version is known:

```text
map backup:          >= 1.15.0
plan end time:       >= 1.15.13
nest-edge:           >= 1.16.0
incremental plans:   >= 1.16.15
maintenance UI:      >= 1.16.20
```

For N8 DND/scheduling we therefore still need the real mower firmware plus its current `time_setting.json` before deciding between the full and incremental `mow_regular` envelopes.

## Voice shared-schema clue

The M9 Pro capture exposes:

```json
{
  "voice_status": {
    "name": "",
    "progress": 0,
    "state": ""
  }
}
```

and `device_config.volume`.

The 2.15.16 app independently contains the MGS `voice_set` command family and the separately downloaded voice-package workflow. Those static facts justify continued N8 voice reverse engineering, but the M9 Pro report does not prove N8 package selection or its report transition.

## Other M9 Pro fields worth checking on N8

The shared-schema capture contains:

```text
device_config.anti_loss_radius
device_config.anti_loss_switch
device_config.camera_switch
device_config.child_lock_switch
device_config.indoor_switch
device_config.log_switch
device_config.pobctl_level
device_config.pobctl_switch
device_config.rain_continue_time
device_config.rain_switch
device_config.volume
grass_state.grass_bag_in_position
grass_state.grass_shield_in_position
ctl_rtk_base.nrtk_base_sdk
ctl_rtk_base.rtk_base_state
voice_status
```

Every one of these should be treated as a candidate read path until a real N8 capture verifies it, unless the field is independently proven by the 2.15.16 N8/MGS app data flow.

## Highest-value real N8 captures

1. full named `property` and `service` shadows while idle;
2. Child Lock OFF -> ON -> OFF in the official app;
3. anti-loss radius at two known values;
4. visual sensitivity Low -> Medium -> High;
5. `time_setting.json` before and after one DND edit;
6. map-manager archive before and after one dumping-area add/edit/delete;
7. state during and after one successful grass dump;
8. voice-package list/selection request and resulting `voice_status` transition;
9. deliberate RTK mode change while physically present with the mower.

Until those captures exist, destructive or uncertain writers remain unexposed.
