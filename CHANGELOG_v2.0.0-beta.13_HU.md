# Anthbot Map v2.0.0-beta.13 – magyar változásnapló

## Javítva

- Tesztelt, háromlépcsős parancsvisszajelzés: parancs elküldve, a felhő
  elfogadta, majd a robot állapotváltozással visszaigazolta.
- A zónanyírás visszaigazolásakor a magyar `nyírás` állapotot is felismeri.
- Integrációváltáskor automatikusan az elérhető, akár számozott Anthbot
  gombentitást választja.
- Az üzenet kisebb és szolidabb, asztali és mobil nézetben is látható.
- A stabil erőforrás-URL miatt HACS-frissítéskor nem kell átírni a Lovelace
  erőforrást.

## Telepítés

A Lovelace-erőforrás ajánlott címe:

```text
/anthbot-map-v2/anthbot-map-card.js
```

Frissítés után indítsd újra a Home Assistantot, majd végezz kényszerített
böngészőfrissítést.
