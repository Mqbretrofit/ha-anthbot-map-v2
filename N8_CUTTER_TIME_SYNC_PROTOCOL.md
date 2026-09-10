# ANTHBOT N8 / MGS cutter-height and time-sync protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the real ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

## Global cutting height

The current MGS Device Settings screen reads the reported property:

```text
cutter_height
```

as a direct scalar and opens a dedicated `CuttingHeightModal`.

### Exact picker values

The modal contains exactly nine values:

```text
30 mm
35 mm
40 mm
45 mm
50 mm
55 mm
60 mm
65 mm
70 mm
```

So the current app range is:

```text
minimum: 30 mm
maximum: 70 mm
step:     5 mm
```

This exactly matches the existing Home Assistant `mow_height_setting` limits.

### Exact writer

The current app does **not** use `param_set {cutter_height: ...}` for this global MGS setting. The dedicated writer is HBC function `34440` and publishes:

```json
{
  "cmd": "ctl_cutter",
  "data": 45
}
```

where `data` is the selected integer height in millimetres.

The save data-flow passes the selected modal value unchanged to that writer. The writer subscribes before publishing, waits for the reported `cutter_height`, and has a 30-second timeout. Its failure text is `strCuttingSettingFailed`.

The current MGS UI blocks this write when the mower is shut down/offline and also respects the PIN-correct state.

### Home Assistant N8 correction

The existing shared HA number already has the correct 30..70/5 mm range, but it calls:

```text
param_set {cutter_height: value}
```

for all mower families.

To preserve Genie/M5/M9/M9 Pro behavior, the N8-only transport now translates **only** the exact one-field payload:

```text
param_set {cutter_height: value}
```

into:

```text
ctl_cutter value
```

Other N8 `param_set` payloads remain unchanged.

The N8 status adapter also mirrors a direct reported `cutter_height` into `param_set.cutter_height` only for N8, allowing the existing HA number entity to read the current value without changing the shared entity implementation.

## `local_time`

The app has multiple current MGS paths that publish the same local-time structure through:

```text
cmd: local_time
```

The data object is exactly:

```json
{
  "time_zone": 7200,
  "year": 26,
  "month": 9,
  "day": 10,
  "hour": 11,
  "minute": 44,
  "second": 0,
  "week": 4
}
```

The values above are only an example. The field semantics reconstructed from the bytecode are:

- `time_zone`: local UTC offset in **seconds**, calculated as `-getTimezoneOffset() * 60`;
- `year`: full year minus 2000;
- `month`: 1..12;
- `day`: day of month;
- `hour`: local hour;
- `minute`: local minute;
- `second`: local second;
- `week`: Monday=1, Tuesday=2, ... Sunday=7.

The weekday conversion is explicitly implemented by indexing:

```text
[7, 1, 2, 3, 4, 5, 6]
```

with JavaScript `Date.getDay()` (Sunday=0).

This is a normal `publishDeviceCommand`/service command path, but no Home Assistant time-sync write is currently needed or exposed.

## `sync_position`

A separate app flow obtains the phone's current location and sends:

```json
{
  "cmd": "sync_position",
  "data": {
    "lat": "<latitude as string>",
    "lon": "<longitude as string>",
    "time": 1789033440
  }
}
```

The location object provides `coords.latitude`, `coords.longitude`, and `timestamp`. The app converts latitude/longitude to strings and stores `Math.trunc(timestamp / 1000)` as seconds.

Important transport distinction: this recovered path calls a lower-level `write` function after `getCurrentPosition`; it is **not** the same `publishDeviceCommand` path used by normal cloud/service commands. It also subscribes through `subscribeMessage` and uses a 5-second timeout.

Therefore `sync_position` must not be blindly added to the N8 cloud service-shadow transport. It likely belongs to a local/BLE positioning workflow and needs transport identification before any Home Assistant implementation.

## Exposure policy

- Global cutter-height routing is corrected N8-only because the app writer, payload, reported state and allowed values are statically complete and the HA entity already existed.
- `local_time` remains unexposed because Home Assistant currently has no need to force mower clock writes.
- `sync_position` remains unexposed and un-routed because its recovered transport is local/lower-level rather than the normal cloud writer.

The published `v2.4.6-beta.11` tag and `release/v2.4.6-beta.10` remain untouched.
