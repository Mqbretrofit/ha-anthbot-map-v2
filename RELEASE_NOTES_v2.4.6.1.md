# Anthbot Map v2.4.6.1

Small stable hotfix for v2.4.6.

## Fixed

- Adds **Allow read-only developer requests** as a third switch under **Anthbot Map → Settings → Development and diagnostics**.
- The switch controls the same existing, opt-in read-only Developer Agent permission used by the separate consent popup.
- Users who did not receive or dismissed the separate popup can now enable or disable developer requests later from the normal integration settings.
- Anonymous usage statistics, automatic diagnostics, and read-only developer access remain three independent permissions.
- Developer requests remain restricted to the integration's built-in read-only probe whitelist; arbitrary code and mower-control commands are not permitted.
- Existing Battery Saver settings and unrelated integration options are preserved when these permissions are changed.

## Compatibility

- No mower-control, mapping, path, zone, Genie, M-series, N8, Battery Saver, or cloud-control behavior is changed by this hotfix.
- The Developer Agent remains disabled by default until explicitly enabled by the Home Assistant administrator.

# Anthbot Map v2.4.6.1 – magyar összefoglaló

Ez a v2.4.6 kis stabil hibajavító kiadása.

## Javítva

- A **Anthbot Map → Beállítások → Fejlesztés és diagnosztika** oldalon megjelent harmadik kapcsolóként a **Csak olvasási fejlesztői lekérések engedélyezése**.
- A kapcsoló ugyanazt a meglévő, önkéntesen engedélyezhető Developer Agent jogosultságot kezeli, mint a külön engedélykérő popup.
- Aki nem kapta meg vagy korábban bezárta a külön popupot, most később is be- vagy kikapcsolhatja ezt a normál integrációs beállításokból.
- Az anonim használati statisztika, az automatikus diagnosztika és a csak olvasási fejlesztői hozzáférés továbbra is három egymástól független engedély.
- A fejlesztői lekérések továbbra is kizárólag az integrációba előre beépített read-only probe-listából futhatnak; tetszőleges kód és robotvezérlő parancs nem küldhető.
- A Battery Saver és minden más, nem kapcsolódó integrációs beállítás változatlanul megmarad az engedélyek módosításakor.

## Kompatibilitás

- A hotfix nem módosítja a robotvezérlést, térképet, útvonalat, zónákat, Genie/M-széria/N8 működést, Battery Savert vagy a felhős vezérlést.
- A Developer Agent alapértelmezetten továbbra is ki van kapcsolva, amíg a Home Assistant adminisztrátora kifejezetten nem engedélyezi.
