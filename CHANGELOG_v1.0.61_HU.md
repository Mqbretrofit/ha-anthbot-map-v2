# Anthbot Map v1.0.61 – magyar változáslista

## Javítások

- Mind a 23 támogatott nyelv teljes fordítást kapott: a fő felület,
  a beállítások, a kalibrálás, az állapotok, a parancsok és a hibaüzenetek
  egyik nyelvnél sem esnek vissza hiányzó kulcs miatt angol szövegre.
- A magyar START, STOP és HOME gombfeliratok is magyarul jelennek meg.
- A `boundary_width: 1` most valóban vékony, egypixeles raszteres
  határvonalat jelent, függetlenül a térkép eredeti felbontásától.
- A tiltott zóna felirata többé nem tapad a látható térkép széléhez:
  a zónával együtt mozog, és a zóna középpontjának eltűnésekor elrejtőzik.
- A felirat csak addig látszik, amíg a tiltott zóna poligonja metszi a
  látható térképet.
- Minden frontendmodul egységes `v137` gyorsítótár-verziót kapott, így a
  böngésző biztosan nem használja a korábbi, szélhez rögzítő rajzolót.

## Telepítés

1. Másold a csomag `www/anthbot-map` mappájának tartalmát ide:
   `/config/www/anthbot-map/`
2. A Lovelace-erőforrás címe legyen:
   `/local/anthbot-map/anthbot-map-card.js?v=137`
3. Mentsd a beállítást, majd frissítsd az oldalt `Ctrl+F5` billentyűkkel.
