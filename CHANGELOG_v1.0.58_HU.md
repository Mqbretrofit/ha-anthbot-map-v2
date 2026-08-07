# Anthbot Map v1.0.58 – magyar változáslista

## Háttérben frissülő lenyírt terület

- A gyári Genie alkalmazás működésével azonos `req_all_path` parancs kerül
  kiküldésre `data: 1` értékkel.
- Az integráció a friss felhős útvonalfájl letöltése előtt megvárja a
  `path_time` módosulását.
- Aktív nyírás közben a feltöltési kérés legfeljebb 10 másodpercenként fut.
- A lenyírt terület frissítéséhez többé nem szükséges megnyitni az Anthbot
  mobilalkalmazást.

## Megbízhatóbb robotvezérlés

- A nyírási és dokkolási parancsok előtt az integráció felébreszti a robot
  felhőkapcsolatát, majd ellenőrzi a friss shadow-választ.
- Sikertelen felhőkapcsolat esetén nem küld vakon újabb indítási parancsot.
- A térképkártya jelzi a felhő és a robot kapcsolatának állapotát.
- A kártya visszajelzi a parancs elküldését és annak robotállapotból
  megállapítható végrehajtását.

## Egyéb javítások

- A fűnyírási magasság szolgáltatásválasztója Home Assistant-kompatibilis
  szöveges opciókat használ.
- A kiválasztott kártyanyelv a felület többi beállításával együtt megmarad.
- A kártya gyorsítótár-verziója `v127`.

## Frissítés

1. HACS használatakor telepítsd a v1.0.58 kiadást, majd indítsd újra a
   Home Assistantot.
2. A Lovelace-erőforrás címe legyen:
   `/local/anthbot-map/anthbot-map-card.js?v=127`
3. Ha a régi felület marad látható, frissítsd a böngésző vagy a Home Assistant
   mobilalkalmazás gyorsítótárát.
