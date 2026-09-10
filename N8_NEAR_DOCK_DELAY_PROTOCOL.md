# ANTHBOT N8 / MGS near-dock and mowing-delay protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the real ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

This document separates protocol recognition from Home Assistant exposure. The two commands documented here are routed through the isolated N8 native transport, but no new HA entity is exposed until live N8 validation confirms the reported state and physical behavior.

## Near-charger / near-dock mowing switch

The current MGS settings screen reads:

```text
near_chg_mow_ctl
```

and renders the switch as ON only when the reported scalar equals `1`.

The switch handler sends the inverse of the current value:

```text
current near_chg_mow_ctl == 1 -> send 0
otherwise                     -> send 1
```

The exact writer is HBC function `34503`. Its literal object is:

```json
{
  "cmd": "ctl_near_chg_mow",
  "data": "<caller supplied>"
}
```

The screen's toggle data-flow proves that the caller-supplied value is the scalar integer `0` or `1`. Therefore the exact normal app payload is:

```json
{
  "cmd": "ctl_near_chg_mow",
  "data": 1
}
```

or:

```json
{
  "cmd": "ctl_near_chg_mow",
  "data": 0
}
```

The writer subscribes before publishing and waits for `near_chg_mow_ctl` to be present in the reported state. Its main timeout is 30 seconds.

The current UI also blocks the action while the mower is shut down/offline and shows the standard device-offline/shutdown messages.

### Important distinction

`ctl_near_chg_mow` is the on/off control for the near-charger mowing feature. It is separate from:

```text
nest_mow_start
nest_mow_stop
nest_param_set
```

`nest_param_set` controls the around-dock task parameters (`cutter_height`, `mow_count`, `pobctl_switch`, `pobctl_level`), while `ctl_near_chg_mow` controls whether the near-charger mowing feature itself is enabled.

## Delayed mowing

The current rain/delay settings screen reads the reported scalar:

```text
mow_delay_time
```

The screen treats zero/falsy as **Off**. For non-zero values it displays hours by dividing the reported value by `60` and applying `Math.floor`. This is consistent with the actual picker values recovered below and proves that the protocol value is expressed in **minutes**.

### Exact picker choices

The 2.15.16 `DelayMowTimeModal` contains a fixed four-item array:

```text
3 hours -> 180
2 hours -> 120
1 hour  -> 60
Off     -> 0
```

So the current production UI permits exactly:

```text
0, 60, 120, 180 minutes
```

The modal initializes its selected value from the reported `mow_delay_time`, stores the picker value directly, and on Save passes that selected scalar unchanged to the screen's `onSaveDelayMowTime` callback.

The screen then passes the value unchanged to the command wrapper.

### Exact wire payload

The command writer is HBC function `34509`. Its literal object is:

```json
{
  "cmd": "mow_delay",
  "data": "<caller supplied>"
}
```

Because the complete UI data-flow is now recovered, the normal app payloads are exactly:

```json
{"cmd":"mow_delay","data":0}
{"cmd":"mow_delay","data":60}
{"cmd":"mow_delay","data":120}
{"cmd":"mow_delay","data":180}
```

The writer subscribes before publishing, waits for `mow_delay_time` to be present in the reported state, and has a 30-second timeout. The app's timeout error text is `Failed to set delay mow time`.

### Modal behavior

The current modal exposes:

```text
delayMowTime
visible
onRequestClose
onSaveDelayMowTime
```

and uses a picker whose `selectedValue` is the current scalar. When the modal becomes visible, its local state is reset from the incoming `delayMowTime`. Save forwards the local selected value to `onSaveDelayMowTime` and then closes the modal.

## Home Assistant policy

Both commands are now included in the isolated N8 native transport command set:

```text
ctl_near_chg_mow
mow_delay
```

This prevents any future use from falling through the legacy Genie command path.

No public HA control is added yet. Before exposing them on a real N8, capture read-only state and verify:

1. idle `near_chg_mow_ctl` before/after toggling the official switch;
2. idle `mow_delay_time` before/after selecting Off / 1 h / 2 h / 3 h;
3. whether the N8 firmware reports the values directly or inside `{value: ...}` envelopes;
4. whether any firmware/version gate hides either feature;
5. physical semantics of near-charger mowing before adding an end-user switch.

The published `v2.4.6-beta.11` tag and `release/v2.4.6-beta.10` are not modified by this work.
