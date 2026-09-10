# ANTHBOT N8 / MGS anti-loss protocol

Status: statically reconstructed from the real ANTHBOT Android app `2.15.16` Hermes HBC98 bundle.

## Reported fields

The current MGS settings hook reads the following values from `device_config`:

```text
anti_loss_switch
anti_loss_radius
```

The Find Robot / anti-theft screens consume the same radius through the `setAntiLossRadius` hook.

## Current write path

The current MGS settings path updates anti-loss values through the generic:

```text
cmd: device_config
```

For the radius the object is:

```json
{
  "anti_loss_radius": 50
}
```

The isolated N8 adapter therefore accepts the integration-level `anti_loss_radius` call and translates it to the current app-native `device_config` payload.

## Exact radius validation

The 2.15.16 UI callback parses the input as base-10 integer and rejects values below **50** with the `safe_distance_limit` message.

The TextInput change callback:

1. removes every non-digit character using `[^0-9]`;
2. parses the remaining value as base-10 integer;
3. clamps values greater than **500** to the string `"500"`.

Therefore the production app range is proven as:

```text
minimum: 50 m
maximum: 500 m
step:    integer metres
```

The display appends the literal unit `m`.

## Home Assistant exposure

Because both the current writer and the exact input range are now statically proven, `feature/n8-support` exposes an N8-only number entity:

```text
Anti-loss alarm radius
50..500 m
step 1 m
```

The entity is not created for Genie, M5, M9 or M9 Pro. The existing N8 anti-loss enable switch remains separate.

Live N8 validation is still useful to confirm the reported value updates immediately on the owner's firmware, but the previous unknown-upper-bound blocker is removed.

The published `v2.4.6-beta.11` and the separate `release/v2.4.6-beta.10` branch remain untouched.
