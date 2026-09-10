# ANTHBOT N8 / MGS Do Not Disturb protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

The schedule object itself is now substantially reconstructed. The exact current cloud/file write endpoint is **not yet proven**, so DND remains intentionally disabled in Home Assistant.

## `usePlan` surface

The current planning hook returns these actions/data:

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

The writer constructs this schedule shape:

```json
{
  "start_time": "<dynamic>",
  "end_time": "<dynamic>",
  "active": "<dynamic>",
  "unlock": 0,
  "week": [1, 2, 3, 4, 5, 6, 7],
  "repeat": 1,
  "workmode": 0
}
```

The values for `start_time`, `end_time` and `active` come from the caller. The remaining values above are the defaults constructed by the current 2.15.16 app path.

The week array is explicitly the seven-element sequence:

```json
[1, 2, 3, 4, 5, 6, 7]
```

## Add/edit logging

The same path constructs an operation log object:

```json
{
  "start_time": "<dynamic>",
  "end_time": "<dynamic>",
  "active": "<dynamic>",
  "action": "add"
}
```

or:

```json
{
  "start_time": "<dynamic>",
  "end_time": "<dynamic>",
  "active": "<dynamic>",
  "action": "edit"
}
```

and passes event name:

```text
dnd_set
```

to the app analytics/logging path.

Important: `dnd_set` is therefore proven as a **log/event identifier**. It must **not** be assumed to be a mower service-shadow command.

## Plan/time data structure

The schedule update pipeline writes/merges these top-level keys:

```text
no_disturb
appointment
```

The deletion path uses:

```text
delete_no_disturb
delete_appointment
```

The DND screen also consumes `timeUrl` and `dnd.nodistrurb`, which is strong evidence that DND is integrated into the plan/time-file workflow rather than the current `device_config` settings writer.

## Current interpretation

What is proven:

- the DND schedule object shape;
- its fixed defaults (`unlock=0`, all seven weekdays, `repeat=1`, `workmode=0`);
- the caller supplies start/end/active;
- add/edit are distinguished by the logging action;
- the plan data uses `no_disturb` / `appointment` plus matching deletion keys;
- `dnd_set` is used by the logging path.

What is **not** yet proven:

- the exact REST/presigned-file write endpoint used by the current MGS DND screen;
- the complete enclosing time-file JSON structure;
- whether the same time-file format is returned unchanged by every N8 firmware;
- the server-side acknowledgement/version/update mechanism after save;
- whether changing DND causes a shadow field, plan id or time-file timestamp to update.

## Home Assistant exposure policy

Do not add a DND write entity yet.

Highest-value live N8 capture:

1. obtain the current read-only time/plan data;
2. change exactly one DND interval in the official app;
3. obtain the same data again;
4. compare `no_disturb`, `appointment`, plan/time metadata and any changed shadow fields;
5. capture only the request shape/endpoint needed for the schedule save, without exposing credentials.

Once that confirms the enclosing object and write route, the recovered schedule object above can be implemented in an N8-only adapter without changing Genie/M5/M9/M9 Pro routing.