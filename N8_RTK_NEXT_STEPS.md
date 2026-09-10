# N8 RTK next validation targets

Static ANTHBOT 2.15.16 analysis has already recovered the cloud command constructors:

```text
ctl_rtk_base 1 = NRTK
ctl_rtk_base 2 = RTK
ctl_rtk_base 3 = Auto
req_rtk_base_info {}
```

The remaining work is live N8 validation rather than command-name guessing.

1. Capture a real N8 idle property/service shadow and record any `ctl_rtk_base`, `rtk_base`, `rtk_state`, `nrtk_*`, `satellite_*` fields.
2. Open the official RTK/base-station screen without changing anything and compare before/after to see what `req_rtk_base_info {}` adds or refreshes.
3. While physically present with the mower, change exactly one mode in the official app: Auto -> RTK or Auto -> NRTK.
4. Confirm whether the N8 acknowledgement is `ctl_rtk_base.rtk_base_state` and whether values remain 1/2/3 on that firmware.
5. Confirm there is no additional BLE/local pairing step or setup precondition.
6. Keep `sync_position` outside cloud routing; its recovered app path uses lower-level local/write semantics and includes phone location.

The existing M9 Pro capture containing `ctl_rtk_base.rtk_base_state` and `nrtk_base_sdk` is a shared-schema clue only, not N8 confirmation.

No public Home Assistant RTK selector should be enabled until steps 1-5 are satisfied.
