# ANTHBOT N8 / MGS03 voice protocol notes

Status: static ANTHBOT Android 2.15.16 reconstruction plus shared-schema live clues. The current package-list API, signed-download request and `voice_set` payload are now statically recovered. Public Home Assistant voice-package selection remains disabled until a real N8 validates package compatibility and report-side behavior.

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

## Current 2.15.16 package-list API

Direct HBC98 data-flow reconstruction identifies the package-list wrapper as function `#15706` (`list`). It calls the application's API client's `get` method with the fixed resource:

```text
GET /voice/package/language
```

No explicit request body is supplied by this wrapper.

The selectable packet objects consumed by the current Voice Settings flow contain at least:

```text
id
english_name
sex
md5
version
vp_url
```

The app can identify the currently selected packet either by packet `id` or by the combined key:

```text
<english_name>_<sex>
```

## Voice Settings hook and writer

Direct parsing identifies the current MGS voice hook:

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

The async writer behind it is function `#27405`. It builds:

```json
{
  "cmd": "voice_set",
  "data": "<caller supplied package object>"
}
```

and publishes through the normal MGS `publishDeviceCommand` path with a 30-second command timeout.

The Voice Settings component (`#15701`) stores `setupVoicePacket` in its environment and its package-selection generator (`#36081`) supplies the exact object described below. This closes the previous gap between the command wrapper and the UI-selected package metadata.

## Exact `voice_set.data` payload

The current 2.15.16 package-selection generator constructs exactly these fields before calling `setupVoicePacket`:

```json
{
  "music_package": "<selected packet id>",
  "english_name": "<selected packet english_name>",
  "sex": "<selected packet sex>",
  "music_url": "<fresh presigned URL>",
  "music_md5": "<selected packet md5>",
  "category": "voice_pack",
  "version": "<selected packet version>"
}
```

Field provenance is statically traced as:

```text
music_package <- packet.id
english_name  <- packet.english_name
sex           <- packet.sex
music_url     <- presigned_url returned by signed-URL request
music_md5     <- packet.md5
category      <- literal "voice_pack"
version       <- packet.version
```

Therefore the complete current cloud command is:

```json
{
  "cmd": "voice_set",
  "data": {
    "music_package": "<packet.id>",
    "english_name": "<packet.english_name>",
    "sex": "<packet.sex>",
    "music_url": "<presigned_url>",
    "music_md5": "<packet.md5>",
    "category": "voice_pack",
    "version": "<packet.version>"
  }
}
```

The isolated N8 transport now recognizes `voice_set` so a future validated N8 package install cannot fall through to Genie/M5/M9/M9 Pro routing. The command is passed through unchanged by the N8 normalization layer. This is transport recognition only; no public HA voice selector is added yet.

A pure helper in `models/n8_voice_payload.py` mirrors the recovered object shape without publishing anything. Its tests deliberately use dummy URLs and identifiers; it exists to prevent future live-validation code from re-inventing or reshaping the proven wire object.

## Signed package download URL

Before constructing `voice_set.data`, the same package-selection generator requests a fresh signed URL. The request object is statically reconstructed as:

```json
{
  "sn": "<device serial>",
  "category": "voice",
  "sub_category": "",
  "filename": "<derived from packet.vp_url>"
}
```

The response field consumed by the flow is:

```text
presigned_url
```

and that value becomes `music_url` in the final `voice_set` payload.

The filename is derived from `packet.vp_url` through an app helper. The exact helper's filename-normalization behavior is not needed to establish the command shape and is intentionally not guessed here. The pure helper therefore accepts the already-derived filename instead of attempting to duplicate unknown normalization.

## Report-side state semantics recovered from the app

The current hook reads `voice_status.state` and explicitly handles at least:

```text
downloading
success
```

When state is `downloading`, increasing `voice_status.progress` updates the visible install progress. When state becomes `success`, the local progress is reset to zero.

The current package identity is derived from `voice_status.name` when available, with `music_package` used as a fallback.

These are application-side expectations. Because the only available live `voice_status` capture is from an M9 Pro, a real N8 still needs to confirm that its firmware reports the same state/progress fields during an install.

## Legacy music-language normalization

The current bundle also contains compatibility normalization for older `music_cfg.music_language` names. Recovered aliases include:

```text
girl_zh -> Chinese_girl
girl_en -> English_girl
girl_de -> German_girl
girl_it -> Italian_girl
girl_es -> Spanish_girl
girl_au -> Australian_girl
girl_fr -> French_girl
```

This is useful for interpreting existing report-side state but is not used as evidence for an N8 package writer by itself.

## Validation boundary

The wire schema is no longer the blocker. A public selector remains disabled because a package installation downloads and applies mower firmware resources. Before exposing that action, a real N8 must confirm that the package list is applicable to the device and that the recovered state/acknowledgement lifecycle matches its firmware.

Specifically validate:

- `/voice/package/language` returns packages applicable to that N8/account/region;
- the selected packet's `vp_url` can be converted by the app flow into a usable signed URL;
- the recovered `voice_set` payload is accepted unchanged by that N8 firmware;
- `voice_status.state` / `progress` transition as expected;
- checksum/version failures and incompatible package behavior are safe;
- current-package identification is stable after reconnect/restart.

## Highest-value real N8 capture

With the owner physically present, capture the package selection sequence:

1. package-list response from `/voice/package/language`;
2. property shadow before selection;
3. signed-URL request/response with credentials and signed query parameters redacted;
4. service-shadow request containing `voice_set`;
5. property shadow while `voice_status.progress` changes;
6. final property shadow after installation.

Do not commit account credentials, serial numbers, signed URL query strings or PIN values.

Until that capture exists, the integration keeps voice-package control research-only even though the current 2.15.16 command payload is now fully reconstructed.
