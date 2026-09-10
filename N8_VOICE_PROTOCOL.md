# ANTHBOT N8 / MGS03 voice protocol notes

Status: static ANTHBOT Android 2.15.16 evidence plus shared-schema live clues. Voice-package writing is intentionally not exposed yet.

## Live-data provenance

The currently available property-shadow capture containing:

```json
{
  "voice_status": {
    "name": "",
    "progress": 0,
    "state": ""
  },
  "device_config": {
    "volume": 100
  }
}
```

belongs to an **Anthbot M9 Pro**, not an N8. It is therefore a useful shared-MGS schema clue only; it does not prove that an N8 firmware reports the identical voice state.

The current Home Assistant volume control remains separate from voice-package selection.

## Direct 2.15.16 Hermes evidence

The real ANTHBOT 2.15.16 Android XAPK contains a Hermes HBC98 bundle. Direct parsing identifies the current MGS voice hook:

```text
function #15705: useVoicePacket
```

That hook reads these voice-related state keys:

```text
volume
music_package
voice_status
music_cfg
music_language
```

and creates the current voice-package writer closure:

```text
function #27402: setupVoicePacket
```

The async writer behind it is function `#27405`. Its bytecode constructs an object with shape:

```text
cmd
data
```

whose first literal is exactly:

```text
voice_set
```

and then publishes it through the normal MGS `publishDeviceCommand` path. Therefore the current service command envelope is statically proven as:

```json
{
  "cmd": "voice_set",
  "data": "<dynamic package payload>"
}
```

The command name/envelope is no longer inferred from strings alone. What remains unresolved is the exact dynamic `data` object passed into `setupVoicePacket` for each selectable package.

## Voice-package API evidence

The older reconstructed application bundle exposes the separately downloaded voice-package language resource:

```text
/voice/package/language
```

The base APK itself does not contain the spoken audio files. Voice assets are downloaded separately, so package metadata/manifest data are required to reconstruct package selection safely.

Related application identifiers include:

```text
voice_status
voice_pack_downloading
voice_pack_option
voice_resource_not_exist
voice_settings
voice_volume_set
music_package
music_cfg
music_language
```

## What is still not proven

Do not expose an N8 voice-package selector until the current 2.15.16 data flow or a real N8 capture proves all of the following:

- exact request method and parameters used to list N8/MGS03 packages;
- model/category filtering applied to the package list;
- exact fields inside the dynamic `voice_set.data` value;
- package identifier/name/version/checksum fields;
- download URL acquisition and expiry behavior;
- expected N8 `voice_status.state` and `progress` transitions;
- rollback/failure behavior when a package is unavailable or incompatible.

The exact `{cmd:"voice_set", data:<dynamic>}` envelope is proven, but the dynamic package payload must not be guessed.

## Highest-value real N8 capture

With the owner physically present, capture the property/service shadows while selecting a different official voice in the ANTHBOT app. The useful sequence is:

1. property shadow before selection;
2. package-list API response/metadata if available;
3. service shadow request containing `voice_set`;
4. property shadow while `voice_status.progress` changes;
5. final property shadow after installation.

Do not include account credentials, signed download query strings or PIN values in committed fixtures.

Until that capture exists, the integration keeps voice-package control research-only and does not guess the dynamic writer payload.
