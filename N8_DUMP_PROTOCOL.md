# ANTHBOT N8 / MGS03 dumping-area protocol (2.15.16 static analysis)

Status: **wire format recovered statically; Home Assistant write UI remains disabled until a real N8 validates it against the cloud and persisted map archive.**

This file documents the current ANTHBOT 2.15.16 Android XAPK path. It is kept on `feature/n8-support`; it does not change `release/v2.4.6-beta.10` or the already published `v2.4.6-beta.11` tag.

## Native dump-area object

The MGS map bridge stores a dumping area in the native `t4/e` object. The fields relevant to the current bridge are:

```text
id          int
name        String        # native overlay/UI field
remote      boolean
eid         int           # constructor default: -1
warningType int
disable     boolean
vertices    List<t4/t>
```

The app's actual React Native serializer emits each dumping area as:

```json
{
  "vertexs": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
  "id": 500,
  "grassId": 500,
  "eid": -1,
  "remote": false,
  "disable": false,
  "warningType": 0
}
```

Notes:

- `vertexs` is the spelling used by the app and protocol.
- `id` and `grassId` are emitted from the same native integer field.
- `eid` defaults to `-1` in the native constructor unless another path supplies it.
- `remote`, `disable` and `warningType` are emitted on every serialized object.
- the native parser requires `id` and `vertexs`; it accepts optional `remote`, `eid` and `disable`.
- the native serializer does **not** emit `name`. `addGrass(id, name, isRemote)` stores `name` for the native overlay, while the current cloud-write path passes the serialized object above. HBC comparison code can read `name`, but that does not make it a required field in the current native write object.

## Vertex format and units

Each vertex is exactly a two-element integer array:

```text
[x_mm, y_mm]
```

The map converter's forward transform is:

```text
x_mm = int((x_transformed * resolution + minX) * 1000)
y_mm = int((y_transformed * resolution + minY) * 1000)
```

The inverse path is:

```text
x_transformed = (x_mm * 0.001 - minX) / resolution
y_transformed = (y_mm * 0.001 - minY) / resolution
```

followed by the map matrix transform.

The native `MapInfo` object labels these fields explicitly as `resolution`, `minX` and `minY`, so the stored dumping-area coordinate integers are map/world coordinates in **millimetres**, not screen pixels and not latitude/longitude.

## Geometry created by the official app

For a new dumping area the native map UI creates a square. The display-side length is calculated as:

```text
mapOverlayScale / mapResolution * 1.5
```

which corresponds to a **1.5 m x 1.5 m** square in map/world space.

The four rectangle corners are taken in this order before coordinate conversion:

```text
left,top
right,top
right,bottom
left,bottom
```

If the overlay is rotated, all four points are rotated around the rectangle centre first. Each resulting point is then converted to `[x_mm, y_mm]` using the transform above.

Therefore an ordinary app-created dumping area has four integer millimetre corner pairs in `vertexs`.

## ID allocation

The current app allocates dumping-area IDs with the generic `getNewId` helper using bounds:

```text
500 .. 599
```

The save path also explicitly filters for this range.

## Normal add/edit save

The native `topGrassAreaSubmit` event carries:

```text
nativeEvent.grasses
```

where each member is the serialized native dump-area object shown above.

The HBC handler keeps changed dumping areas and calls `updateGrassAreas(changedAreas, [])`. `updateGrassAreas` then sends the generic area writer:

```json
{
  "cmd": "area_set",
  "data": {
    "dump_grass_areas": [
      {
        "vertexs": [[0, 0], [0, 0], [0, 0], [0, 0]],
        "id": 500,
        "grassId": 500,
        "eid": -1,
        "remote": false,
        "disable": false,
        "warningType": 0
      }
    ],
    "delete_dump_areas": []
  }
}
```

The generic `area_set` writer waits for the map `area_id` update and uses a **30-second timeout**.

The zero coordinates above are placeholders showing the object shape only; real writes must use the map-derived millimetre coordinates.

## Delete save

The native delete event provides `nativeEvent.grassId`. The HBC handler calls:

```text
updateGrassAreas([], [grassId])
```

so the outgoing write is:

```json
{
  "cmd": "area_set",
  "data": {
    "dump_grass_areas": [],
    "delete_dump_areas": [500]
  }
}
```

Thus `delete_dump_areas` is an array of integer dumping-area IDs.

## Remote dumping-area creation

The native remote path creates the same `t4/e` object with `remote=true`, computes the same four-point geometry and emits `topReportRemoteGrass` with:

```text
nativeEvent.grasses
```

The current HBC handler forwards that array directly to `setupRemoteGrass`, which sends:

```json
{
  "cmd": "ctl_building_dump",
  "data": {
    "dump_grass_areas": [
      {
        "vertexs": [[0, 0], [0, 0], [0, 0], [0, 0]],
        "id": 500,
        "grassId": 500,
        "eid": -1,
        "remote": true,
        "disable": false,
        "warningType": 0
      }
    ],
    "state": "build_dump_set"
  }
}
```

`setupRemoteGrass` reads the current shadow `map.area_id`, subscribes for the update and uses a **120-second timeout**.

The remote lifecycle commands are:

```text
ctl_building_dump {state: build_dump_init}
ctl_building_dump {state: build_dump_continue}
ctl_building_dump {state: build_dump_finish}
ctl_building_dump {dump_grass_areas: [...], state: build_dump_set}
```

The init/continue/finish operations use 10-second timeouts in the app.

## Static validation rules already recovered

The official MGS UI prevents invalid dumping-area placement, including:

- lawn boundary;
- electronic bridge;
- restricted/no-go area;
- charging-dock area;
- less than 1 m from the inner lawn boundary;
- the 0.5 m strip immediately outside the boundary;
- geometry not fully inside the plot boundary;
- centre outside the map;
- dumping areas within 1 m of each other;
- incompatible active tasks.

Remote creation also requires the mower to begin inside the mapped area.

## What is still required before enabling Home Assistant writes

Static analysis is now sufficient to build the payload correctly, but write exposure remains intentionally blocked until a real N8 capture confirms:

1. the cloud accepts the recovered 2.15.16 `area_set` object unchanged;
2. the resulting `map_manager_<SN>.tar.gz -> area_setting.json` persists the expected subset/shape;
3. `area_id` changes as expected after add/edit/delete;
4. the real mower applies the 1.5 m geometry with the same map coordinate frame;
5. warning/error behavior is understood well enough to avoid exposing unsafe placement.

Recommended live validation is a before/after `area_setting.json` capture around one harmless dumping-area add, then one edit and one delete in the official app.
