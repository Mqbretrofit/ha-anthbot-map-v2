# Anthbot Map v1.0.60 – magyar változáslista

## Újdonság

- A **Tiltott zónák megjelenítése** kapcsoló a teljes tiltott területet
  elrejti vagy megjeleníti.
- A meglévő **Tiltott zóna feliratok** kapcsoló továbbra is csak a feliratot
  szabályozza.
- Mindkét kapcsoló állapota megmarad az oldal frissítése után.
- YAML-ban a teljes tiltott zónaréteg a `show_no_go_zones: false`
  beállítással rejthető el.

## Telepítés

1. Másold a csomag `www/anthbot-map` mappájának tartalmát ide:
   `/config/www/anthbot-map/`
2. A Lovelace-erőforrás címe legyen:
   `/local/anthbot-map/anthbot-map-card.js?v=134`
3. Mentsd a beállítást, majd frissítsd az oldalt `Ctrl+F5` billentyűkkel.
