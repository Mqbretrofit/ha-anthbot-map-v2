# ANTHBOT N8 / MGS Do Not Disturb protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

The schedule object and current service-shadow command are now substantially reconstructed. DND writes remain intentionally disabled in Home Assistant until the firmware-versioned plan format is validated on a real N8.

## Storage/read path: `time_setting.json`

The current MGS map-manager workflow explicitly handles:

```text
/time_setting.json
```

alongside `iot_map.bin`, `iot_bridge.bin` and `area_setting.json`.

The local per-device plan path is built as:

```text
/time_<serial>.json
```

and the downloaded `time_setting.json` is read with `readFile` + `JSON.parse` before updating plan state. The map shadow also exposes `plan_id`, which is tracked by the refresh pipeline.

This establishes `time_setting.json` as the read-side schedule/DND file in the map-manager ecosystem.

## `usePlan` surface

The current planning hook returns:

```text
add
edit
remove
plans
dnd
nodistrurb
deletePlan
```

The DND writer is the app function named `nodistrurb`.

Its caller-facing input contains:

```text
start_time
end_time
active
```

## Exact DND schedule object

The writer constructs:

```json
{
  "start_time":"<dynamic>",
  "end_time":"<dynamic>",
  "active":"<dynamic>",
  "unlock":0,
  "week":[1,2,3,4,5,6,7],
  "repeat":1,
  "workmode":0
}
```

The caller supplies `start_time`, `end_time` and `active`. The other values above are fixed by the current 2.15.16 DND path.

`unlock` is also the discriminator used by `usePlan`:

```text
unlock == 0  -> Do Not Disturb entry
unlock != 0  -> normal mowing appointment/schedule
```

The planner keeps at most one `unlock == 0` DND entry when normalizing a save.

## Exact service-shadow writer: `mow_regular`

Direct HBC98 data-flow reconstruction now proves the current writer.

The command is:

```json
{
  "cmd":"mow_regular",
  "data":{
    "value":"<plan value/list>",
    "timezone":"<UTC offset hours>",
    "timezone_sec":"<UTC offset seconds>"
  }
}
```

The current app computes:

```text
timezone_sec = -Date().getTimezoneOffset() * 60
timezone     = timezone_sec / 3600
```

The command subscribes for its response and uses a 10,000 ms timeout.

A second recovered publishing path normalizes the complete plan object first and then sends:

```json
{
  "cmd":"mow_regular",
  "data":<normalized plan object>
}
```

so `mow_regular` is no longer inferred from analytics or filenames: it is the statically proven service command used by the schedule pipeline.

## Full/legacy plan envelope

The non-incremental plan shape is:

```json
{
  "timezone":"<hours>",
  "timezone_sec":"<seconds>",
  "value":["<schedule objects>"]
}
```

The `value` list can contain the DND object above and normal mowing appointments.

The plan pipeline also uses the semantic groups:

```text
no_disturb
appointment
delete_no_disturb
delete_appointment
```

These are internal/update-path groupings; they must not be confused with the final service command name.

## Incremental plan format

The current application contains a firmware-gated incremental writer. Its envelope is:

```json
{
  "timezone":"<hours>",
  "timezone_sec":"<seconds>",
  "version":"<plan version>",
  "value":["<changed schedule object>"]
}
```

Static feature gate for `isPlanIncrementEnabled`:

```text
app version >= 2.9.0
AND mower fw_version.system_version >= 1.16.15
```

Debug builds bypass the normal app-version gate. Since the analysed app is 2.15.16, the relevant release-build uncertainty for an N8 is its mower firmware version.

A related `isPlanEndTimeEnabled` gate requires:

```text
app version >= 2.8.0
AND mower firmware >= 1.15.13
```

This version split is the main reason DND writing is still not exposed from Home Assistant: a writer must choose the correct full vs incremental envelope and preserve the current plan version semantics rather than blindly replacing the whole schedule.

## Add/edit logging

The DND UI also emits analytics data shaped like:

```json
{
  "start_time":"<dynamic>",
  "end_time":"<dynamic>",
  "active":"<dynamic>",
  "action":"add|edit"
}
```

with event name:

```text
dnd_set
```

`dnd_set` is therefore an analytics/event identifier, **not** the mower service command. The actual service command is `mow_regular`.

## App-side default schedule time helper

`getPlanParam` calculates suggested UI defaults; it is not the persisted wire schema itself.

The app chooses roughly:

```text
before 08:00       -> 08:00
08:00..10:00       -> next minute
10:00..16:00       -> 16:00
16:00..18:00       -> next minute
after 18:00        -> 08:00 next day
```

Its next-minute calculation is based on seconds from midnight:

```text
hour * 3600 + (minute + 1) * 60
```

and its weekday conversion maps Sunday to 7.

These are UI convenience defaults, not constraints that Home Assistant needs to reproduce.

## What is now proven

- read-side schedule file: `time_setting.json` in the map-manager workflow;
- local cache naming: `/time_<serial>.json`;
- DND schedule object and fixed defaults;
- `unlock == 0` distinguishes DND from normal schedules;
- full envelope `{timezone, timezone_sec, value}`;
- incremental envelope `{timezone, timezone_sec, version, value}`;
- exact service-shadow command `mow_regular`;
- timezone formulas;
- 10-second response timeout;
- incremental-plan firmware threshold `1.16.15` for this app;
- end-time firmware threshold `1.15.13` for this app;
- `dnd_set` is analytics only.

## Still requiring live N8 validation

Do not add a DND write entity yet. We still need a real N8 to confirm:

1. its current `time_setting.json` shape and `version` value;
2. its firmware and therefore which plan writer path is active;
3. before/after `plan_id` when one DND interval is changed;
4. whether an incremental DND edit sends only the changed DND object or additional retained entries on that firmware;
5. response/report fields after `mow_regular` save.

The safest next implementation is read-only parsing/diagnostics of `time_setting.json`; write support can then be enabled N8-only after one before/after owner capture without affecting Genie/M5/M9/M9 Pro.
