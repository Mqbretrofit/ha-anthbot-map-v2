# Anthbot Map v2.4.2 – magyar változáslista

## Egyéni gombok mentése és akkukímélő javítások

- Bekerültek a robotonként, Home Assistantban mentett egyéni
  kártyagomb-műveletek; a korábbi YAML `button_actions` beállítás továbbra is
  használható.
- Home Assistant szolgáltatás, script és célentitás is megadható úgy, hogy az
  eredeti ANTHBOT parancsok tartalék működése megmarad.
- Másik töltő-okoskonnektor kiválasztásakor az 55+1 perces anti-shutdown
  védelem azonnal az új konnektorhoz igazodik.
- A százalékok egyszerű módosítása nem indítja újra feleslegesen a futó
  55 perces időzítést.
- A hibásan eltárolt régi százalékértékeket használat előtt biztonságosan
  korrigálja.
- Minden meglévő profil, a 23 fordítás, a vezérlések, a közös/külön RTK-kezelés
  és az újraindítás utáni állapotmentés változatlanul megmaradt.

