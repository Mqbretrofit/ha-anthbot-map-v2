# Anthbot Map v1.0.59 – magyar változáslista

Ez a kiadás a GitHub #1 hibajelentésben felsorolt konfigurációs és
megjelenítési problémákat javítja.

## Javítások

- A YAML `language` beállítása most felülírja a böngészőben korábban
  elmentett nyelvet.
- Az angol felületen nem maradnak magyar vezérlőfeliratok.
- A `boundary_color` és `boundary_width` a dekódolt raszteres határvonalra is
  érvényes.
- Húzás és pásztázás után a kártya nem értelmezi a mozdulatot kattintásként.
- A nagy térkép bezárógombja bal felső, mindig elérhető helyre került, a
  kártya nagy nézetben nem vágja le.
- A tiltott zónák címkéi nem lógnak ki a vászonról.
- A `show_no_go_labels: false` beállítással a tiltott zónák feliratai
  elrejthetők, miközben a zónák továbbra is láthatók.
- A robotkép eredeti képpontjai és külső átlátszó háttere megmaradt, de a
  hibás belső átlátszó részek megszűntek.

## Frissítés

1. Telepítsd a v1.0.59 integrációt, majd indítsd újra a Home Assistantot.
2. A Lovelace-erőforrás címe legyen:
   `/local/anthbot-map/anthbot-map-card.js?v=133`
3. Frissítsd a böngésző vagy a Home Assistant alkalmazás gyorsítótárát.
