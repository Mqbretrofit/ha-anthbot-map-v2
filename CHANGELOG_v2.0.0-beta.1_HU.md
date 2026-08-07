# Anthbot Map v2.0.0-beta.1 – magyar változásnapló

Kiadás dátuma: 2026-08-07

## Béta tesztverzió

- Az integráció külön `anthbot_map` domaint és
  `/config/custom_components/anthbot_map/` mappát használ.
- Nem írja felül a Vincent-, Adrian- vagy korábbi Genie Plus-integráció
  fájljait.
- A régi és az új integráció egyszerre telepítve maradhat, ezért eltávolítás és
  újratelepítés nélkül lehet közöttük váltani.

> [!CAUTION]
> A két Anthbot-integrációt ne engedélyezd egyszerre. Az Anthbot Map tesztelése
> előtt tiltsd le a régi integráció konfigurációs bejegyzését. Egyidejű
> futtatásuk egymással versengő felhőkapcsolatokat és ütköző robotparancsokat
> okozhat.

## Visszaállítás

Az előző állapot visszakapcsolásához tiltsd le az Anthbot Map integrációt,
engedélyezd újra a korábbi Anthbot-integrációt, majd indítsd újra a Home
Assistantot. A korábbi integráció fájljai és konfigurációja megmaradnak.

## Fontos

- A béta integráció új eszköz- és entitásbejegyzéseket hoz létre.
- Ha a régi integráció entitásai megmaradtak a nyilvántartásban, az új
  entitásazonosítók `_2` végződést kaphatnak.
- Ez béta tesztverzió; éles automatizálások átállítása előtt készíts Home
  Assistant biztonsági mentést.
