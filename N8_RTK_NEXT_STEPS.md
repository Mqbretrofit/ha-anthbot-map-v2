# N8 RTK next static-analysis targets

1. Recover the exact constructor for `ctl_rtk_base`.
2. Recover the exact constructor for `req_rtk_base_info`.
3. Identify acknowledgement fields and response-state values.
4. Identify whether the command changes RTK base power, pairing/configuration or both.
5. Keep `sync_position` outside cloud routing unless a service-shadow path is proven.
