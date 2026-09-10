# N8 RTK read-only capture plan

For a real N8/MGS03, collect these values before enabling any RTK write:

- `rtk_state`
- `rtk_base_state`
- `ctl_rtk_base`
- any `rtk_*`, `base_*`, `gnss_*`, `satellite_*`, `position_*` scalar fields
- named-shadow keys before and after opening the RTK/base-station screen in the official app
- result of the app's read/info action if it triggers `req_rtk_base_info`

Do **not** send `ctl_rtk_base`, `sync_position`, pairing, reset, location-write or mapping commands for this capture.

Goal: identify the acknowledgement/report fields and distinguish simple RTK power control from pairing/configuration before adding any Home Assistant writer.
