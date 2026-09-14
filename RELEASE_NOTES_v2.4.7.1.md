# Anthbot Map v2.4.7.1

Cloud/API resilience hotfix for temporary ANTHBOT backend failures.

## Changes

- Treats ANTHBOT application-level `code=5xx` responses as temporary cloud failures even when the HTTP request itself returned 200.
- Adds bounded retry/backoff for task-event history requests such as `/api/v1/device/v2/code/list`.
- Keeps existing IoT STS retry behavior and now correctly classifies JSON `code=500` responses so the retry path can run.
- Coalesces short task-event failure bursts and rate-limits repeated Home Assistant warnings for the same cloud error.
- Adds opt-in `cloud_api_error` diagnostics so temporary ANTHBOT backend outages can appear in Anthbot Reports without exposing credentials or raw cloud response bodies.
- Recent startup cloud failures can be replayed to the reporting observer after Home Assistant finishes platform setup, avoiding lost early-boot diagnostics.
- No mower command routing, map/path parser, Battery Saver decision logic, or model-specific control path was changed.

This release addresses the failure pattern reported in issue #40 (`Invalid task event response (code=500)`) and the same ANTHBOT-cloud pattern observed on the IoT STS endpoint (`IoT STS returned code=500`).

# ANTHBOT Map v2.4.7.1 – magyar változások

Átmeneti ANTHBOT cloud/API hibák kezelését javító stabilitási hotfix.

- A HTTP 200 mellett JSON-ban érkező ANTHBOT `code=5xx` hibákat ideiglenes cloud hibának kezeli.
- A task-event history lekérés kontrollált retry/backoffot kapott.
- Az IoT STS JSON `code=500` most már bekerül a meglévő retry útvonalba.
- Az ismétlődő azonos HA warningok ritkítva vannak.
- Az opt-in diagnosztika `cloud_api_error` riportot küldhet az Anthbot Reports felé, credential és nyers cloud response nélkül.
- A robotvezérlés, map/path feldolgozás és Battery Saver döntési logika nem változott.
