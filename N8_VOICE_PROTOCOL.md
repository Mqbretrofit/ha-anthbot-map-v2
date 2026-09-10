# ANTHBOT N8 / MGS03 voice protocol notes

Status: read-side/live evidence plus static application evidence. Voice-package writing is intentionally not exposed yet.

## Real N8 report-side evidence

A real N8 property-shadow capture reports:

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

This confirms that the N8 firmware has the same report-side concepts needed for voice-package download/install progress and volume control.

The current Home Assistant volume control remains separate from voice-package selection.

## Application evidence

The reconstructed ANTHBOT application protocol contains the command family:

```text
voice_set
```

and the older application bundle exposes the voice-package language resource:

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
```

## What is not proven yet

Do not expose an N8 voice-package selector until the current 2.15.16 data flow proves all of the following:

- exact request method and parameters used to list N8/MGS03 packages;
- model/category filtering applied to the package list;
- exact `voice_set` data object;
- package identifier/name/version/checksum fields;
- download URL acquisition and expiry behavior;
- expected `voice_status.state` and `progress` transitions;
- rollback/failure behavior when a package is unavailable or incompatible.

A literal `voice_set` command name is not enough to infer these values.

## Highest-value live capture

With the owner physically present, capture the property/service shadows while selecting a different official voice in the ANTHBOT app. The useful sequence is:

1. property shadow before selection;
2. package-list API response/metadata if available;
3. service shadow request containing `voice_set`;
4. property shadow while `voice_status.progress` changes;
5. final property shadow after installation.

Do not include account credentials, signed download query strings or PIN values in committed fixtures.

Until that capture exists, the integration keeps voice-package control read-only/research-only and does not guess a writer.
