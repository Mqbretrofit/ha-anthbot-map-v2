# Anthbot Map v2.4.6.3

This release adds full opt-in, read-only Developer Agent diagnostics so future troubleshooting does not require an integration update for every new field or problem.

## Added

- `full_state` for complete credential-redacted reported state, including internal/private keys.
- `full_diagnostics` for full state plus safe runtime snapshots and object inventories.
- `state_inspector` for parameterized read-only inspection of nested state/runtime paths.
- `state_diff` for baseline/diff diagnostics of live changes.
- `refresh_diagnostics` for a read-only property refresh followed by full diagnostics.
- Client capability advertisement and safe job parameters for future server-side diagnostic queries.

## Safety

- Developer Agent opt-in remains required.
- No mower-control commands are added.
- No arbitrary Python, URL, HTTP, MQTT, method or property execution is added.
- Credential-like fields and sensitive identifiers remain redacted/protected.
