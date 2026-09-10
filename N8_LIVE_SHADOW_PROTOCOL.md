# ANTHBOT N8 / MGS03 live property-shadow evidence

Status: read-only evidence from a real N8 capture, correlated with the ANTHBOT Android 2.15.16 static protocol reconstruction.

No account credentials, serial number, location coordinates or PIN values are recorded in this document.

## Confirmed Child Lock report field

The real N8 property shadow reports the physical-panel Child Lock as:

```json
{
  "device_config": {
    "child_lock_switch": 0
  }
}
```

This supersedes the earlier diagnostic placeholder name `device_config.child_lock`.

It is also independent of:

```json
{
  "ui_lock": {
    "value": 0
  }
}
```

Static 2.15.16 analysis already showed that `ui_lock` participates in the generic command/device-lock guard. It must not be treated as the mower-panel Child Lock.

The integration now normalizes the observed read-side value to:

```text
_n8_child_lock
```

No Child Lock write command is exposed yet. A report field does not prove the command/payload used to change it.

## Confirmed RTK report shape

The same real N8 reports:

```json
{
  "ctl_rtk_base": {
    "nrtk_base_sdk": 2,
    "rtk_base_state": 3
  }
}
```

This matches the statically reconstructed 2.15.16 selector mapping:

```text
1 = NRTK
2 = RTK
3 = Auto
```

The integration now keeps read-only normalized aliases:

```text
_n8_rtk_base_state
_n8_nrtk_base_sdk
```

The exact cloud commands `ctl_rtk_base` and `req_rtk_base_info` remain N8-native in the transport, but no public Home Assistant RTK selector is enabled until an intentional live command/acknowledgement test is performed.

## Real firmware and feature-gate implications

The captured N8 reports mower system firmware:

```text
1.0.42
```

That version is below several feature thresholds recovered from the current 2.15.16 app:

```text
map backup:          >= 1.15.0
plan end time:       >= 1.15.13
nest-edge:           >= 1.16.0
incremental plans:   >= 1.16.15
maintenance UI:      >= 1.16.20
```

Therefore features found in the application bundle must not automatically be assumed to be enabled on this N8 firmware.

For DND/scheduling in particular, this firmware does not meet the incremental-plan threshold. The likely path is the legacy/full `mow_regular` plan envelope, but write support still stays disabled until the mower's actual `time_setting.json` is captured and a before/after DND edit confirms preservation semantics.

## Voice report shape

The real N8 exposes:

```json
{
  "voice_status": {
    "name": "",
    "progress": 0,
    "state": ""
  }
}
```

and the same property shadow exposes `device_config.volume`.

The app protocol contains the `voice_set` command family and the earlier application analysis identified the separately downloaded voice-package system. This is enough to confirm that N8 has the report-side voice machinery, but not enough to invent a package-install payload or expose voice-pack selection in Home Assistant.

## Other observed N8 property fields

The read-only capture also confirms the current MGS-style configuration grouping, including:

```text
device_config.anti_loss_radius
device_config.anti_loss_switch
device_config.camera_switch
device_config.indoor_switch
device_config.log_switch
device_config.pobctl_level
device_config.pobctl_switch
device_config.rain_continue_time
device_config.rain_switch
device_config.volume
grass_state.grass_bag_in_position
grass_state.grass_shield_in_position
```

These observations support the existing N8-only normalization and keep the implementation separate from Genie/M5/M9/M9 Pro.

## Next live captures

Highest-value safe captures are:

1. full property/service shadow before and after toggling Child Lock in the official app;
2. `time_setting.json` before and after one DND edit;
3. map-manager archive before and after one dumping-area edit;
4. voice package list/selection request and the resulting `voice_status` transition;
5. deliberate `ctl_rtk_base` mode change while physically present with the mower.

Until those captures exist, destructive or uncertain writers remain unexposed.
