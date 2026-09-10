# Anthbot Map v2.4.6.2

Small stable reporting hotfix for v2.4.6.1.

## Fixed

- Anonymous usage statistics now send a lightweight `heartbeat` whenever the integration starts or reloads, but only when **Share anonymous usage statistics** is enabled.
- The heartbeat refreshes the reporting server with the integration version that is actually running, together with the already-approved anonymous Home Assistant/model/count metadata.
- This fixes installations that could remain shown on an old beta or stable version in Anthbot Reports after a HACS update.
- Heartbeat delivery is non-blocking and does not affect mower control, mapping, Battery Saver or startup if the reporting server is unavailable.
- No heartbeat is sent when anonymous usage reporting is disabled.

## Compatibility

- No mower-control, map, path, zone, Genie, M-series, N8, Battery Saver or cloud-control behavior is changed by this hotfix.
- Existing reporting and Developer Agent permissions remain independent.

# Anthbot Map v2.4.6.2 – magyar összefoglaló

Ez a v2.4.6.1 kis stabil riportolási hibajavítása.

## Javítva

- Ha az **Anonim használati statisztika megosztása** engedélyezve van, az integráció minden induláskor vagy újratöltéskor egy kis `heartbeat` riportot küld.
- A heartbeat frissíti a Reporting Servert a ténylegesen futó integrációverzióval, valamint a már engedélyezett névtelen Home Assistant-/modell-/darabszám adatokkal.
- Ezzel javul az a hiba, amikor HACS-frissítés után az Anthbot Reports még egy régi béta vagy stabil integrációverziót mutatott.
- A heartbeat háttérben fut, nem blokkolja az integráció indulását, és nincs hatással a robotvezérlésre, térképre vagy Battery Saverre akkor sem, ha a riport szerver éppen nem elérhető.
- Kikapcsolt anonim statisztika mellett heartbeat sem kerül elküldésre.

## Kompatibilitás

- A hotfix nem módosítja a robotvezérlést, térképet, útvonalat, zónákat, Genie/M-széria/N8 működést, Battery Savert vagy a felhős vezérlést.
- A statisztikai riportolás és a Developer Agent engedélyei továbbra is egymástól függetlenek.
