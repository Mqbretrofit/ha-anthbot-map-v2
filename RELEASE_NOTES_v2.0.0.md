# Anthbot Map v2.0.0

## First stable v2 release

This is the stable release of the field-tested `v2.0.0-beta.15` source. No
integration-code changes were made after that tested build.

## Highlight: much faster live AWS IoT/MQTT updates

The integration maintains a persistent AWS IoT MQTT-over-WebSocket shadow
connection. During field testing it made mower state, position, heading,
battery, and status updates arrive substantially faster than periodic HTTP
polling alone.

### What is included

- Service commands prefer the active MQTT channel.
- If MQTT is unavailable, commands automatically fall back to the signed AWS
  IoT HTTP publish endpoint.
- Reconnects include bounded retry, account reauthentication, and short-lived
  STS credential refresh recovery.
- Signed WebSocket URLs and credentials are redacted from logs and diagnostics.
- Rapid shadow updates are coalesced before they reach Home Assistant, avoiding
  the client WebSocket backlog observed in early testing.
- HTTP remains as a safety layer: five-minute reconciliation while MQTT is
  connected and conservative one-minute polling while it is offline.
- The map entity and bundled card expose MQTT online/offline diagnostics.
- Map archive integrity and refresh diagnostics are more robust.

This release is built from the field-tested `test27` package. The separately
distributed Hungarian voice package is intentionally not included.

> Keep only one Anthbot integration enabled at a time. The old integration may
> remain installed for rollback, but disable it before enabling Anthbot Map and
> restart Home Assistant when switching.
