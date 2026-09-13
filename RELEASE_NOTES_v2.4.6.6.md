# Anthbot Map v2.4.6.6

Startup hotfix built directly on v2.4.6.5.

## Fixed

- Fixed Home Assistant startup waiting on the long-lived ANTHBOT Developer Agent task until the bootstrap timeout.
- The Developer Agent loop is now registered with `ConfigEntry.async_create_background_task()` instead of `hass.async_create_task()`, so it no longer participates in Home Assistant's startup barrier.
- The existing Developer Agent behavior, consent flow, reporting endpoints, probe whitelist, and mower control paths are unchanged.
- Added regression coverage to prevent the long-lived agent from being registered again as a startup-blocking task.

## Validation

The fix was tested on a live Home Assistant installation. After restart, the previous `Setup timed out for bootstrap waiting on ... anthbot_developer_agent_...` warning no longer appeared, and Home Assistant completed its final startup phase normally.

## Scope protection

This release changes only the Home Assistant client-side Developer Agent task registration. The separate `Mqbretrofit/anthbot-reporting-server` project is not part of this hotfix.

# ANTHBOT Map 2.4.6.6 – változások

Ez a kiadás egy célzott indítási hotfix a 2.4.6.5 stabil verzióhoz.

## Javítva

- Megszűnt az a hiba, amely miatt a Home Assistant indulása az ANTHBOT Developer Agent hosszú életű feladatára várt egészen a bootstrap timeoutig.
- A Developer Agent loop most `ConfigEntry.async_create_background_task()` segítségével indul a korábbi `hass.async_create_task()` helyett, ezért már nem része a Home Assistant indulási várakozási körének.
- A Developer Agent működése, engedélykérése, riport végpontjai, read-only probe whitelistje és a robotvezérlési útvonalak nem változtak.
- Regressziós teszt védi, hogy ez a hosszú életű feladat később ne kerülhessen vissza startupot blokkoló taskként.

## Ellenőrzés

A javítást valódi Home Assistant telepítésen teszteltük. Újraindítás után a korábbi `Setup timed out for bootstrap waiting on ... anthbot_developer_agent_...` figyelmeztetés eltűnt, és az indítás utolsó fázisa normálisan befejeződött.

## Hatókör

Ez a hotfix kizárólag a Home Assistant oldali Developer Agent task-regisztrációt módosítja. A külön `Mqbretrofit/anthbot-reporting-server` projekt nem része ennek a javításnak.
