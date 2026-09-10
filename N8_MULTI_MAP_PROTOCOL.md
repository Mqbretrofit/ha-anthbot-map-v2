# ANTHBOT N8 / MGS multi-map and sub-map protocol

Status: static reverse-engineering notes for `feature/n8-support`.

Source: direct analysis of the ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

This document records the protocol without exposing destructive Home Assistant controls. Map backup/restore, backup deletion and sub-map deletion remain intentionally disabled until a real N8 validates the live state and coordinate frame.

## `multi_map_ctl` wire format

The current app uses one generic command for map-backup operations:

```json
{
  "cmd": "multi_map_ctl",
  "data": {
    "sub_cmd": "<operation>",
    "id": "<optional backup id>"
  }
}
```

The fixed command string and nested `sub_cmd` / `id` object are reconstructed directly from the HBC98 command builder.

The generic helper receives the mower serial number, `sub_cmd`, and an optional `id`. When `id` is undefined, JavaScript serialization omits it from the transmitted object.

## Backup operations

### Create/save backup

The app's `creatBackup` flow calls the generic writer with:

```text
sub_cmd = save_map
```

and no backup ID. The resulting wire payload is therefore:

```json
{
  "cmd": "multi_map_ctl",
  "data": {
    "sub_cmd": "save_map"
  }
}
```

### Delete backup

```json
{
  "cmd": "multi_map_ctl",
  "data": {
    "sub_cmd": "delete_map",
    "id": "<backup id>"
  }
}
```

### Restore backup

```json
{
  "cmd": "multi_map_ctl",
  "data": {
    "sub_cmd": "restore_map",
    "id": "<backup id>"
  }
}
```

### Update/overwrite backup

```json
{
  "cmd": "multi_map_ctl",
  "data": {
    "sub_cmd": "update_map",
    "id": "<backup id>"
  }
}
```

## Reported `multi_maps` state

The app reads the named-shadow `multi_maps` object. Static analysis proves these fields are consumed:

```text
multi_maps.map_list
multi_maps.state
multi_maps.time
```

Backup-list entries use at least:

```text
id
map_file_name
md5
time_stamp
```

The UI passes the selected backup entry's `id` to delete/restore/update operations.

The command-response path treats `state == -1` as failure. The current completion logic is more specific than a simple success boolean:

- `save_map` watches for the backup list length to change and then requires the `multi_maps.state` completion bit `2` to be set (`state & 2 == 2`);
- `update_map` watches the first backup entry's MD5 for a change and likewise requires the completion bit `2`;
- `delete_map` watches the backup list length for a change;
- `restore_map` watches map state / `map_id` rather than only the backup list.

These observations explain which reported fields are useful in a live before/after capture without assigning undocumented meanings to every numeric `state` value.

The app commonly reads the first `map_list` entry in the backup UI. This is not enough evidence to claim a server-side maximum backup count.

## Timeouts / polling

The current HBC98 `multi_map_ctl` writer:

- subscribes to the mower state before publishing;
- polls state at roughly 1.5-second cadence in the relevant path;
- uses a 61-second operation timeout for save/update and related completion handling;
- publishes through the normal `publishDeviceCommand` path.

These timings are implementation observations, not a guarantee that every N8 firmware responds with identical latency.

## `delete_sub_map` wire format

The app contains a separate destructive sub-map deletion command:

```json
{
  "cmd": "delete_sub_map",
  "data": {
    "point": [
      [0, 0],
      [100, 200]
    ]
  }
}
```

The input array is cloned point-by-point as:

```text
point.map(p => [p[0], p[1]])
```

before being placed in the command object. No coordinate conversion is performed inside the recovered `delete_sub_map` writer itself.

Therefore static analysis proves that the command forwards an array of 2D coordinate pairs, but it does **not** by itself prove whether the upstream screen supplies map/world millimetres, transformed map coordinates, or another frame. A real N8 capture is required before this command can be exposed safely.

## `delete_sub_map` completion behavior

Two app generations coexist in the bundle:

- an older path monitors `map_time`, `map_tar_time`, and `bt_map_time`;
- the newer MGS path monitors `map.map_id` / map state and polls while waiting for completion.

The command constructor has a main 30-second timeout plus a short auxiliary timeout. The newer path also uses a roughly 2-second interval while checking map state.

## Home Assistant exposure policy

The N8 transport recognizes `multi_map_ctl` and `delete_sub_map` so these commands cannot accidentally fall through to legacy Genie routing. Recognition does **not** mean the integration exposes buttons for them.

Keep all of these writes disabled until live N8 validation:

- save backup;
- overwrite/update backup;
- restore backup;
- delete backup;
- delete sub-map.

Restore/delete operations can materially alter the user's mower map and must not be guessed from static analysis.

## Safe live validation

The next useful N8 capture is read-only:

1. capture `multi_maps` while the mower is idle;
2. record only structural metadata such as `state`, number of `map_list` entries, backup IDs and entry field names;
3. in the official app create one backup;
4. capture `multi_maps` again;
5. compare the list count/ID/state transitions;
6. only after that, with the owner present, test restore/update/delete behavior if needed.

Do not export presigned URLs, cloud credentials, access tokens or MD5 values just to validate the schema.

For `delete_sub_map`, capture the official app request or before/after map data first so the coordinate frame can be identified without risking the real map.
