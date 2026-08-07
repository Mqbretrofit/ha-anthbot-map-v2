# Anthbot Map – változások a GitHub v1.0.29 és a stabil v1.0.54 csomag között

Összehasonlítás alapja:

- GitHub kiadás: `v1.0.29` (`4d492fd` tag)
- Stabil helyi csomag: `anthbot-app-style-hamburger-menu-v1.0.54.zip`
- Összehasonlítás dátuma: 2026-07-17

## Rövid összefoglaló

A v1.0.54 csomag legfontosabb újdonsága az Anthbot alkalmazáshoz hasonló, felhőből letöltött történeti nyírási útvonal támogatása. A kártya ezen felül megőrzi az aktuális nyírás útvonalát nézetváltás és oldalfrissítés után, külön kezeli a nyírási munkameneteket, és opcionális nyírási lefedettségi sávot rajzol.

## Integráció – Anthbot Genie Plus

### Felhős történeti útvonal

- Bekerült az Anthbot Genie/MGS bináris útvonalformátum dekódolása.
- Támogatott protokollverziók: MGS v1, v2 és v3.
- Kezeli a v1 történeti fejléc eltérő elrendezését és koordináta-skáláját.
- Kezeli a nyers, gzip- és zlib-tömörített útvonalfájlokat.
- A dekódolt pontoknál megmarad:
  - az X/Y koordináta;
  - a pont típusa;
  - az irányszög;
  - v3 esetén a `clean_time` érték.

### Útvonalfájl lekérése

- A rendszer több, az Anthbot felhőben előforduló fájlnevet és alkategóriát is megpróbál:
  - `path`;
  - `his_path`;
  - `history_path`;
  - `record_path`;
  - `history_path_info`.
- Közvetlen, az eszközállapotban kapott történeti URL-ről is képes letölteni az útvonalat.
- Letöltés előtt megpróbálja az alkalmazás által használt történetiútvonal-frissítő parancsokat:
  - `req_history_mapping_path`;
  - `getHisPath`;
  - `ReqHisPath`.
- Aktív nyírás közben 5 másodpercenként kérhet friss történeti útvonalat.
- Felismeri a további aktív állapotokat, például `working`, `cutting`, `edgecutting`, `gototarget` és `remotectrl`.

### Új térképszenzor-attribútumok

- `mower_status`
- `robot_status_raw`
- `cloud_path`
- `mowed_path`
- `path_id`
- `path_start`
- `path_task_type`
- `path_point_count`
- `path_coordinate_scale`
- `path_first_point`
- `path_point_types`
- `history_path_info`
- `history_path_source`
- `history_path_live_refresh`
- `history_path_refresh_interval`
- `history_path_download_source`

Ezek segítségével ellenőrizhető, hogy az útvonal URL-ről vagy előre aláírt felhős letöltésből érkezett, hány pontot tartalmaz, és milyen ponttípusokat adott vissza a robot.

## Anthbot Map kártya

### Lenyesett útvonal megőrzése

- Az élő nyírási útvonal böngészőoldali tárolást kapott.
- Nézetváltás vagy oldalfrissítés után az aktuális munkamenet útvonala visszatölthető.
- A felhős `path_id` vagy `path_time` különválasztja az egyes nyírási munkameneteket.
- Új nyírás indításakor nem keveri automatikusan az előző munkamenet útvonalát az újjal.
- Töltés, dokkolás és hazatérés közben nem rögzít nyírási pontokat.

### Útvonal kirajzolása

- Az útvonalforrás alapértelmezése `auto` lett.
- Elsődlegesen a felhős történeti útvonalat használja, ennek hiányában a tárolt vagy élő útvonalat.
- Több lehetséges felhős mezőből is felismeri az útvonalat.
- Megőrzi a ponttípusokat és a `clean_time` adatot.
- A hibás vagy nem nyírási pontoknál megszakítja a vonalat.
- Nagy koordináta-ugrásnál új szakaszt kezd, így nem köt össze távoli pontokat egyetlen átlóval.
- Külön kezeli a felhős és az élő útvonalréteget.

### Nyírási lefedettségi sáv

- Új, szélesebb és áttetsző lefedettségi réteg került az útvonal mögé.
- Alapértelmezett becsült vágásszélesség: 360 mm.
- Új YAML-beállítások:
  - `show_mowed_coverage`
  - `mowed_coverage_color`
  - `mowed_coverage_width`

### Robot megjelenítése

- A robot képmérete a korábbi térképszélesség-arányos számítás helyett fix alapméretből indul.
- A robot a térkép nagyításával együtt nagyul.
- A pontként rajzolt tartalék robotjelölés méretezése is a zoomhoz igazodik.

### Lebegő hamburger menü

- A kártya megtartja az áttetsző, jobb alsó hamburger menüt.
- A menüfeliratok HTML-entitásos formát kaptak a hibás karakterkódolás elkerülésére.
- A Kalibrálás rész a v1.0.54 csomagban nem kerül be a lebegő panelbe; külön, sötét és világos szövegű blokk marad a kártya alatt.
- A Kalibrálás felirat és alcímek rögzített világos színt kaptak.

## Telepítési és példaállományok

Új fájlok a v1.0.54 csomagban:

- `TELEPITES_APP_MOD.txt`
- `anthbot-map-card/TELEPITES.txt`
- `anthbot-map-card/anthbot-map-card.yaml`
A mellékelt YAML egy teljes, kalibrált mintabeállítást tartalmaz háttérkép-hivatkozással, robotkalibrációval és határvonal-beállításokkal. A saját háttérképet adatvédelmi okból a kiadás nem tartalmazza.

## Módosult fájlok

Integráció:

- `custom_components/anthbot_genie_plus/api.py`
- `custom_components/anthbot_genie_plus/coordinator.py`
- `custom_components/anthbot_genie_plus/sensor.py`
- `custom_components/anthbot_genie_plus/manifest.json`

Kártya:

- `anthbot-map-card.js`
- `renderer.js`
- `calibration.js`
- `styles.css`

Nem változott érdemben többek között az `i18n.js`, `geometry.js`, valamint a vezérlőgombokhoz tartozó integrációs platformok többsége.

## Verziózási megjegyzés

A csomagnevek és a belső verziók jelenleg nem azonosak:

| Elem | GitHub v1.0.29 | Stabil v1.0.54 ZIP |
|---|---:|---:|
| Kiadás/csomag neve | v1.0.29 | v1.0.54 |
| Integráció belső `manifest.json` verziója | 1.0.28 | 1.0.32 |
| Renderer/stílus gyorsítótár-verzió | v101 | v126 |

A következő GitHub-kiadás előtt célszerű a `manifest.json`, a release tag, a ZIP neve, a kártya verziója és a dokumentáció verziószámait egységesíteni.

## Kompatibilitás

- A korábbi Anthbot kártya YAML alapbeállításai továbbra is használhatók.
- Az új lefedettségi opciók nem kötelezőek.
- A teljes felhős történeti útvonalhoz az integráció és a kártya fájljait együtt kell frissíteni.
- Frissítés után Home Assistant-újraindítás és böngésző/app gyorsítótár-frissítés szükséges.
