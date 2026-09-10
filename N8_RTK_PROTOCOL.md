# ANTHBOT N8 / MGS RTK protocol notes

Status: static reverse-engineering notes for `feature/n8-support`.

Source: ANTHBOT Android app `2.15.16` Hermes HBC98 bundle and the isolated N8 transport.

The reporting server has moved to a separate repository; this file continues only the mower/integration reverse-engineering work.

## Known RTK command family

The current MGS/N8 bundle contains the following RTK-related command names:

```text
ctl_rtk_base
req_rtk_base_info
sync_position
```

`sync_position` is not treated as a normal cloud service-shadow command. The recovered app path obtains the phone/device position and uses lower-level `write` / `subscribeMessage` semantics, so it remains outside the N8 cloud transport.

`ctl_rtk_base` and `req_rtk_base_info` are cloud-facing candidates, but their exact data payload and result object still require full constructor/data-flow reconstruction before Home Assistant exposure.

## Safety/exposure policy

Do not expose any new RTK write entity until all of the following are known:

- exact `data` object/scalar shape;
- valid command values;
- reported state field(s) used as acknowledgement;
- whether the operation controls RTK base power, pairing/configuration, or another function;
- firmware/UI gating.

Read-only capture of existing RTK shadow fields is safe and preferred for live validation.
