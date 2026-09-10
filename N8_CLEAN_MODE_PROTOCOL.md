# ANTHBOT N8 / MGS cleaning-mode protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the real ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

This command is intentionally **not exposed as a Home Assistant button yet**. Static analysis proves the wire command and app-side state gating, but the physical action should be verified with an N8 owner present before public exposure.

## Exact command

The current app contains two equivalent MGS writers. Both construct the same fixed payload:

```json
{
  "cmd": "clean_mode_cmd",
  "data": 1
}
```

The writers use the normal `publishDeviceCommand` path, so this is a cloud/service-shadow command family rather than the lower-level/local transport used by e.g. `sync_position`.

The command is now recognized by the isolated N8 native transport so future use cannot fall through to the legacy Genie path.

## App-side preconditions

The current wrapper obtains the mower `mode.value` and permits the cleaning action only when the mower is:

```text
idle
pause
```

It explicitly blocks the action while charging and displays the app's `device_is_charging_hint`. Other incompatible modes display the generic `device_not_idle` message. The wrapper also checks that the mower is online/not shut down before publishing.

This means `clean_mode_cmd` is not a generic command that should be sent during an arbitrary task.

## Response semantics

The subscription callback filters for:

```text
cmd == clean_mode_cmd
```

and then reads the returned command `state`.

Static control-flow reconstruction shows:

```text
state == 3 -> success / resolve
state == 2 -> failure / reject
```

The failure branch raises the translated error identified by:

```text
descending_disk_failed
```

Other states are ignored while waiting for completion.

The command writer uses a **10-second timeout**.

## Interpretation boundary

The error name strongly suggests the command involves positioning/lowering a mower mechanism (the app string is literally `descending_disk_failed`), but that string alone is not enough to claim the exact physical movement or safety behavior of every N8 firmware.

Therefore Home Assistant must not expose this as a normal button until a real N8 owner can verify:

1. what physically happens after `clean_mode_cmd {data:1}`;
2. that `idle` and `pause` are sufficient safe preconditions;
3. what `state` values the N8 firmware actually reports;
4. how the command behaves if connectivity is lost during the action;
5. how the official app tells the user to prepare the mower before entering cleaning mode.

## Home Assistant policy

Current status:

```text
N8 native transport recognition: YES
public HA button:               NO
live N8 validation required:    YES
```

Do not expose the action by copying the generic command into `button.py` before the physical behavior is validated.

The published `v2.4.6-beta.11` tag and the separate `release/v2.4.6-beta.10` branch are untouched by this work.
