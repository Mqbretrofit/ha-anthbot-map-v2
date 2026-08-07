# Anthbot Map v2.0.0-beta.2 – magyar változásnapló

## Javítások

- A kártya az indítás, leállítás és töltőre küldés során a YAML-ban megadott
  natív Home Assistant `button` entitásokat használja.
- A zónák indítása a létrehozott zónagombokon keresztül történik, így nem
  függ a korábbi integráció szolgáltatási domainjétől.
- A kártya automatikusan kiválasztja az aktív `_2`, `_3` vagy későbbi
  entitásokat, az árva `unavailable` bejegyzéseket pedig figyelmen kívül hagyja.
- Az alapértelmezett országkód `+36`, a minimális frissítési idő 10 másodperc.
- Javítva az Anthbot-felhő időbélyegeinek 8 órás eltolódása.
- A kapcsolódási hibák részletes oka megjelenik a Home Assistant naplójában.
- Javítva a Home Assistant 2027.6 előtt elavult `TrackerEntity` import.
- A nagyméretű térkép- és útvonaladatok nem árasztják el a normál naplót.
