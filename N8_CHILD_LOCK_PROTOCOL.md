# ANTHBOT N8 / MGS03 Child Lock protocol

Status: static ANTHBOT Android 2.15.16 evidence plus shared-schema live clues. **No Child Lock write is exposed in Home Assistant yet.**

## What the official UI means by Child Lock

The MGS03 copy describes Child Lock as disabling the mower's physical panel buttons while leaving power and emergency stop functional.

This is not the same feature as the app/device command lock reported through `ui_lock`.

## Shared-schema live clue

An available **Anthbot M9 Pro** property-shadow capture reports:

```text
device_config.child_lock_switch
```

That is useful as a candidate N8 field because the products share parts of the MGS protocol family, but it is not a real N8 capture and does not prove an N8 writer.

## Direct 2.15.16 Hermes result

The real 2.15.16 Android XAPK contains a Hermes bytecode v98 bundle. Direct parsing of its HBC string table and function headers identifies the current MGS hook:

```text
function #15857: useDeviceConfig
```

The hook reads exactly these `device_config` settings:

```text
log_switch
indoor_switch
rain_switch
rain_continue_time
anti_loss_switch
anti_loss_radius
pobctl_switch
pobctl_level
volume
camera_switch
```

The associated selector closure is:

```text
function #27794
```

and reads the same ten fields from `device_config`.

`useDeviceConfig` creates named setting writers/closures including:

```text
switchRainer
switchAntiLoss
setAntiLossRadius
updateVolume
switchIndoor
switchLog
switchVision
setVisionLever
switchCamera
```

There is no Child Lock setter in this hook.

## No literal Child Lock writer in this app build

A complete string-table search of the Hermes bundle finds no literal:

```text
child_lock
child_lock_switch
Child Lock
```

The APK DEX files likewise contain no `child_lock` / `child_lock_switch` writer string.

This matters because the app does contain a generic `device_config` publisher accepting dynamic objects. The existence of that generic writer is **not** enough to conclude that this firmware/app path writes:

```text
device_config {child_lock_switch: 0|1}
```

That payload remains a hypothesis, not a proven command.

## Why `ui_lock` must not be reused

Static HBC98 analysis shows `ui_lock.value == 1` feeds the generic command guard and blocks commands from the app's `DEVICE_LOCK_FORBID_COMMAND` list with the device-locked error path.

Child Lock has different user-facing semantics: it disables physical mower-panel buttons. Therefore Home Assistant must not map `ui_lock` to Child Lock.

## What is needed to finish it

One real N8 owner capture can settle the remaining ambiguity safely:

1. export idle property/service shadow;
2. toggle Child Lock OFF -> ON in the official app;
3. export again;
4. toggle ON -> OFF;
5. export a third time;
6. compare only changed fields and service-shadow acknowledgements.

If `device_config.child_lock_switch` changes and the service request can be observed, the exact N8 writer can then be enabled model-scoped without affecting Genie/M5/M9/M9 Pro.

Until that capture exists, Child Lock stays read-only/candidate-only.
