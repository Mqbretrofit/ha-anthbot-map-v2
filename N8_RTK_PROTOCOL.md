# ANTHBOT N8 / MGS RTK protocol notes

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the ANTHBOT Android app `2.15.16` Hermes HBC98 bundle and the isolated N8 transport.

The reporting server has moved to a separate repository; this file covers mower/integration reverse engineering only.

## Exact RTK/NRTK mode command

The current MGS app exposes three positioning modes in its RTK-mode selector. Static data-flow reconstruction proves the option objects are:

```text
mode 1 -> NRTK
mode 2 -> RTK
mode 3 -> Auto
```

The selector's confirmation handler passes the selected scalar directly into the `switchModel` hook. That hook publishes:

```json
{
  "cmd": "ctl_rtk_base",
  "data": 1
}
```

for NRTK, `data: 2` for RTK, and `data: 3` for Auto.

No wrapping object or coordinate data is added by the command writer.

## Reported state / acknowledgement

The current MGS settings screen reads:

```text
ctl_rtk_base.rtk_base_state
```

and maps it with the same values:

```text
1 -> NRTK
2 -> RTK
3 -> Auto
```

The service-command subscription waits until a report contains a truthy `ctl_rtk_base` object, then resolves the request. The recovered writer uses a 30-second timeout.

This means the live N8 validation target is now narrow: confirm that an N8 reports the same `rtk_base_state` values after changing the mode in the official app.

## Exact RTK base information request

The app's `reqRTKBaseInfo` function publishes the fixed payload:

```json
{
  "cmd": "req_rtk_base_info",
  "data": {}
}
```

The related NRTK hook consumes at least:

```text
rtk_base.rtk_id
rtk_base.state
bt_satellite_time
```

and the surrounding store exposes satellite count/list data. The request itself is read-oriented and contains no coordinates, credentials or user location.

## `sync_position` is a different transport

`sync_position` remains intentionally outside the Home Assistant cloud service-shadow route. The recovered app path first obtains the phone/device position and then uses lower-level `write` / `subscribeMessage` semantics instead of `publishDeviceCommand`.

Do not treat `sync_position` as equivalent to `ctl_rtk_base` or `req_rtk_base_info`.

## Integration policy

`ctl_rtk_base` and `req_rtk_base_info` are now recognized by the isolated N8 native command transport so an N8 call cannot fall through to legacy Genie routing.

Public Home Assistant RTK mode writing is still held back until one live N8 confirms:

- `ctl_rtk_base.rtk_base_state` is present;
- values 1/2/3 correspond to NRTK/RTK/Auto on that firmware;
- switching modes does not require an additional local/BLE step;
- the official app presents no additional safety/setup precondition.

No Genie/M5/M9/M9 Pro routing is changed by this work.
