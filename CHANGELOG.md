# Changelog

## 2.3.0 — 2026-08-21

- Added structured mowing-history cards and per-session map/path detail.
- Switched mowing records to the mobile app's confirmed `/api/v1/device/area`
  endpoint and corrected historical path coordinate scaling.
- Added experimental M5/M9 property-shadow, live-path, status, command, and
  map-archive parsing compatibility; M5/M9 map display is not yet working.
- Fixed multi-mower history targeting, long-session duration conversion, and
  filtering of non-mowing travel segments.
- Removed captured device identifiers and added release/version consistency
  checks.

See `RELEASE_NOTES_v2.3.0.md` and `CHANGELOG_v2.3.0_HU.md` for details.

## 2.2.0 — 2026-08-14

Stable release containing every Anthbot Map improvement since `2.0.0`, plus
real-time app-compatible edge-definition synchronization, mower-confirmed edge
setting saves, support for valid edge records without geometry, and automatic
Lovelace resource registration in storage mode.

See `RELEASE_NOTES_v2.2.0.md` for the complete English change list and
`CHANGELOG_v2.2.0_HU.md` for the complete Hungarian change list.

## 2.1.0 — 2026-08-14

Stable release of the field-tested `2.2.1-beta.48` feature set. Compared with
`2.0.0`, it adds app-style task selection and pause/resume, multi-zone ordering,
complete global/manual/automatic zone settings, maintenance and history views,
editable edge overlap, the Garden Map mobile layout, 23-language localization,
and an MQTT transport aligned with the ANTHBOT Android 2.15.15 application.

See `RELEASE_NOTES_v2.1.0.md` for the complete English change list and
`CHANGELOG_v2.1.0_HU.md` for the complete Hungarian change list.


## 2.2.1-beta.45 — 2026-08-14

- Restored the proven beta.35 command execution route for panel controls.
- Single manual and automatic zone selections again press their concrete zone
  button entity; multi-zone selection and ordering remain available.

## 2.2.1-beta.44 — 2026-08-14

- Fixed rotated `contain` geometry: at ±90 degrees the renderer now fits the
  landscape map against the swapped viewport axes before rotation, instead of
  drawing it at roughly 56% of the available mobile size.

## 2.2.1-beta.43 — 2026-08-14

- Replaced the experimental mobile overrides with the exact mobile layout and
  renderer rules from the supplied working Garden Map Card.

## 2.2.1-beta.42 — 2026-08-14

- Force the map canvas to fill the available mobile viewport even when the
  card has a configured fixed height.
- Detect touch-only mobile and tablet displays in addition to narrow screens.

## 2.2.1-beta.41 — 2026-08-14

- Matched the proven Garden Map Card mobile layout: full available viewport
  map height, compact floating menu, and a 76% scrollable glass panel.
- Added Garden Map compatible `mobile_map_rotation`, `mobile_map_fit`, and
  `mobile_robot_size` options.
- Mobile controls and tabs now use the same compact two-column layout.

## 2.2.1-beta.40 — 2026-08-14

- Panel controls now react reliably to a single mouse click or touch.
- Live mower updates no longer replace a pressed button between pointer-down
  and click events.

## 2.2.1-beta.39 — 2026-08-14

- The manual and automatic zone selectors now preserve their independently
  opened or closed state while selections are changed.
- Selecting three or more zones remains stable and keeps the chosen mowing
  order.
- Zone clicks no longer propagate to the surrounding collapsible section.
- Removed the gray hover flicker from mowing-target buttons while preserving
  the green selected state.

## 2.0.0 — 2026-08-12

First stable Anthbot Map v2 release, promoted from the field-tested
`2.0.0-beta.15` source without integration-code changes.

### Highlight: faster live AWS IoT/MQTT communication

- Added a persistent AWS IoT MQTT-over-WebSocket shadow connection for much
  faster mower state, position, heading, battery, and status updates than
  periodic HTTP polling alone.
- Service commands prefer the active MQTT connection and automatically fall
  back to the signed AWS IoT HTTP publish endpoint if the live transport is
  unavailable.
- Added bounded reconnect, account reauthentication, and short-lived STS
  credential refresh handling without logging signed URLs or secrets.
- Coalesces rapid live-shadow updates before publishing them to Home Assistant,
  preventing the WebSocket message flood seen during early field testing.
- Keeps a five-minute HTTP safety reconciliation while MQTT is connected and a
  conservative one-minute HTTP fallback while it is offline.
- Exposes live MQTT diagnostics on the map entity and shows MQTT online/offline
  status in the bundled map card.
- Added map-definition integrity checking, refresh diagnostics, and redacted
  Home Assistant diagnostic export.
- Built from the field-tested `test27` package. The separately distributed
  Hungarian voice package is intentionally not included.

## 2.0.0-beta.13 — 2026-08-08

- Added tested three-stage command feedback: command sent, cloud accepted and
  mower state confirmed.
- Recognizes Hungarian mower states such as `nyírás`, `töltés`, `készenlét`
  and `vissza a töltőre`, including zone-mowing confirmation.
- Automatically selects available numbered Anthbot button entities when
  switching between supported Anthbot integrations.
- Uses a smaller, accessible feedback message on desktop and mobile.
- Keeps the stable `/anthbot-map-v2/anthbot-map-card.js` resource URL, so HACS
  updates do not require manual Lovelace resource changes.

## 2.0.0-beta.12 — 2026-08-08

- The map card now skips configured related entities that are `unavailable`
  and automatically selects the active numbered or unnumbered Anthbot entity.
- Start, stop, dock and zone commands prefer the automatically discovered
  native Home Assistant button entities.
- Service fallback supports both `anthbot_map` and the legacy
  `anthbot_genie_plus` domain when switching integrations.
- The integration automatically mirrors the bundled map card into
  `/config/www/anthbot-map-v2/`, so the card remains loadable while the v2
  config entry is disabled during legacy integration testing.

## 2.0.0-beta.11 — 2026-08-07

- Sorted every manifest key in the exact order required by Home Assistant hassfest.

## 2.0.0-beta.10 — 2026-08-07

- Fixed manifest key ordering required by Home Assistant hassfest.
- Keeps the integration-served frontend introduced in beta.8, so future HACS updates no longer require manual `/config/www` copying.

## 2.0.0-beta.9 — 2026-08-07

### Fixed

- Az automatikus frontend-kiszolgáláshoz használt Home Assistant `http`
  komponens deklarált integrációs függőség lett; a hassfest ellenőrzés zöld.

## 2.0.0-beta.8 — 2026-08-07

### Changed

- A frontend kártya az integráció része lett, és a HACS-frissítésekkel együtt
  automatikusan frissül.
- Az új, gyorsítótárazás nélküli erőforrás URL:
  `/anthbot-map-v2/anthbot-map-card.js`.

## 2.0.0-beta.7 — 2026-08-07

### Fixed

- Automatikus módban a kártya az `anthbot_map` szolgáltatásokat használja az
  indításhoz, leállításhoz, dokkoláshoz és zónanyíráshoz a bizonytalan
  automatikusan felismert `button` entitások helyett.

## 2.0.0-beta.6 — 2026-08-07

### Fixed

- A kiadási csomagban megsérült `coordinator.py` fájl tiszta UTF-8 forrásból
  újra felkerült, így az integráció ismét importálható.

## 2.0.0-beta.5 — 2026-08-07

### Fixed

- Helyreállt az integráció betöltése azokon a Home Assistant verziókon, amelyek
  még csak a korábbi `TrackerEntity` importútvonalat támogatják.

## 2.0.0-beta.4 — 2026-08-07

### Fixed

- A zónanyírási csempék kapcsolatkimaradás alatt is láthatók maradnak.
- Ha a YAML-ban megadott számozott térképentitás elérhetetlenné válik, a kártya
  automatikusan megkeresi az ugyanahhoz a robothoz tartozó aktív változatot.

## 2.0.0-beta.3 — 2026-08-07

### Fixed

- A zónanyírási csempék akkor is megmaradnak, amikor a térképérzékelő
  átmenetileg `unavailable` állapotú.
- A kártya közvetlenül a natív Home Assistant zónagombokból építi fel a
  zónanyírási lehetőségeket.

## 2.0.0-beta.2 — 2026-08-07

### Fixed

- A kártya vezérlőgombjai a YAML-ban megadott natív `button` entitásokat
  használják, a zónagombok pedig a hozzájuk tartozó Home Assistant
  zónagombot nyomják meg.
- A kártya automatikusan felismeri az aktív `_2`, `_3` vagy későbbi
  entitásváltozatot, és kihagyja az árva `unavailable` entitásokat.
- Az alapértelmezett országkód Magyarország (`+36`), a frissítési idő pedig
  az engedélyezett minimumhoz igazodva 10 másodperc.
- Az Anthbot `YYYYMMDDHHMMSS` időbélyegek helyesen, UTC+8 forrásidőzónából
  kerülnek UTC-re átszámításra.
- A bejelentkezési és eszközfelderítési hibák valódi oka bekerül a naplóba.
- Megszűnt a `TrackerEntity` elavult importjára vonatkozó figyelmeztetés.
- A nagy térkép-, útvonal- és területdiagnosztika csak debug szinten naplózódik.

## 2.0.0-beta.1 — 2026-08-07

### Changed

- Az integráció külön `anthbot_map` domaint és
  `custom_components/anthbot_map` mappát használ.
- A béta a Vincent-, Adrian- és korábbi Genie Plus-integráció mellett is
  telepítve maradhat, ezért eltávolítás nélkül lehet közöttük váltani.
- A térképkártya szolgáltatáshívásai az új `anthbot_map` szolgáltatásdomaint
  használják.

### Safety

- Egyszerre csak egy Anthbot-integráció engedélyezhető; a dokumentáció külön
  tesztelési és visszaállítási útmutatót tartalmaz.
- Az új domain külön eszköz- és entitásbejegyzéseket hoz létre, ezért a béta
  entitásazonosítói `_2` végződést kaphatnak.

### Testing

- A teljes tesztcsomag az új csomagnévvel és útvonallal fut.

## 1.0.70 — 2026-08-07

### Added

- Minden Anthbot robothoz létrejön egy natív Home Assistant `lawn_mower`
  entitás.
- A natív entitásról elindítható a teljes nyírás, leállítható az aktuális
  feladat, és a robot visszaküldhető a töltőre.
- A robot felhőállapota a Home Assistant szabványos nyírás, dokkolás, szünet,
  visszatérés és hiba állapotaira képeződik le.

### Compatibility

- A Genie, M5 és M9 közvetlen, számozott, egyszeresen és többszörösen
  beágyazott státuszformátumai támogatottak.
- Az összes korábbi szolgáltatás, zónanyírás, zónagomb, szenzor, kapcsoló és
  térképfunkció változatlanul elérhető marad.

### Documentation

- Kiemelt figyelmeztetés jelzi, hogy más Anthbot-integrációval nem ajánlott
  párhuzamosan használni, mert duplikált entitásokat, egymással versengő
  felhőkapcsolatokat és ütköző parancsokat okozhat.
- A magyar és angol telepítési leírás egyértelműsíti a régi integráció
  eltávolítását és az esetleg megváltozó entitásazonosítókat.

### Testing

- Új regressziós tesztek ellenőrzik a natív fűnyíró állapotleképezését,
  beleértve az M-szériás beágyazott adatokat és a hibaállapot elsőbbségét.

## 1.0.69 — 2026-08-06

### Fixed

- Az M9 időbélyeges, kétszeresen beágyazott akkumulátoradata helyesen
  százalékértékké alakul.
- Az akkumulátorfeldolgozó tetszőleges számú `value` burkolót biztonságosan
  kibont, és ciklikus vagy hibás adatnál `None` értéket ad.
- A régi közvetlen, az M5 egyszeresen beágyazott és az M9 kétszeresen
  beágyazott akkumulátorformátuma egyaránt támogatott.

### Testing

- Új regressziós tesztek ellenőrzik a Genie, M5 és M9 formátumot, a szöveges
  számot, a hiányzó és tartományon kívüli értékeket, valamint a ciklikus
  burkolót.

## 1.0.68 — 2026-08-04

### Fixed

- A fő `CHANGELOG.md` ismét teljes: bekerültek az 1.0.65, 1.0.66 és 1.0.67
  kiadások korábban külön fájlban szereplő változásai.
- A teljes telepítő ZIP már a naprakész fő változásnaplót tartalmazza.

## 1.0.67 — 2026-08-04

### Added

- Az M5 és M9 LiDAR modellek térképe az alkalmazással azonos `multi_maps`
  archívumból töltődik le.
- A dekóder kezeli a nyers TAR, gzip és zlib tömörítésű térképarchívumokat.
- A térképfájl kiválasztása a készülékfelhő `multi_maps.map_list` adatai alapján
  történik.
- A térkép a fájl, az időbélyeg vagy az MD5 változásakor automatikusan frissül.
- Hiányzó vagy átmenetileg hibás térkép esetén az integráció minden lekérdezési
  ciklusban újrapróbálkozik.
- A korábbi Genie modellek régi térképformátumának támogatása megmaradt.

### Testing

- Tizenhárom automatikus teszt ellenőrzi a nyers TAR, gzip és zlib archívumokat,
  valamint a hibás és hiányos bemenetek kezelését.

### Contributors

- Köszönet @ndoty közreműködéséért, az M5 készüléken végzett ellenőrzésért és a
  tesztekért.

## 1.0.66 — 2026-08-02

### Fixed

- Az M5 Lidar modellek `elec: {"value": ...}` akkumulátor-adatformátuma
  támogatott.
- A korábbi modellek közvetlen `elec: 85` formátuma továbbra is működik.
- Az akkumulátorérték egységesen egész számmá alakul.
- A hiányzó, hibás vagy 0–100 tartományon kívüli érték nem hoz létre érvénytelen
  Home Assistant szenzorállapotot.
- A feldolgozás külön, tesztelhető `_battery_level()` függvénybe került.

## 1.0.65 / map card v140 — 2026-08-02

### Fixed

- A nyírt terület kizárólag az Anthbot-felhőből letöltött munkamenetet használja,
  ugyanazt az adatforrást, mint a gyári alkalmazás.
- Cloud módban megszűnt a böngészőben tárolt korábbi nyomvonal visszatöltése és
  a robot helyzetéből lokálisan felépített élő útvonal rárajzolása.
- A felhős és a helyi útvonal többé nem kerül összefésülésre.

### Changed

- A Lovelace-erőforrás gyorsítótár-verziója `v140`.

## 1.0.64 / map card v138 — 2026-07-31

### Fixed

- A térképkártya a gyári Anthbot alkalmazással egyezően elrejti az előző
  nyírás útvonalát, amikor a robot visszatér a dokkolóhoz vagy tölt.
- A töltés bináris szenzora is bekerül a térkép megjelenítési állapotába, így a
  felhőben maradt régi útvonaladat nem jelenik meg aktív nyírásként.

### Changed

- A Lovelace-erőforrás gyorsítótár-verziója `v138`.

## 1.0.63 — 2026-07-31

### Fixed

- Az AWS IoT STS-hitelesítők lekérése 500, 502, 503, 504, hálózati hiba és
  időtúllépés esetén legfeljebb háromszor próbálkozik, 1 és 3 másodperces
  várakozással.
- Az integráció csak 401/403 hitelesítési hibánál jelentkezik be újra az
  Anthbot-fiókba; átmeneti szerverhibánál nem terheli felesleges
  bejelentkezésekkel a felhőt.
- Korai STS-frissítési hiba esetén a még ténylegesen le nem járt gyorsítótárazott
  hitelesítő használható marad, de lejárt vagy az AWS által már elutasított
  hitelesítő nem kerül újra felhasználásra.
- A napló az egyes átmeneti próbálkozásokat csak debug szinten jelzi, és warning
  bejegyzést csak a próbálkozások kimerülése után ír.
- A `hacs.json` ismét megfelel a jelenlegi HACS-sémának, és az integráció
  tartalmazza a HACS által elvárt helyi márkaikont.

## 1.0.62 — 2026-07-30

### Fixed

- A Home Assistant Recorder többé nem menti el az Anthbot térképszenzor nagy,
  gyorsan változó attribútumait, így megszűnik a 16 384 bájtos állapotattribútum-
  korlát túllépése és az ebből eredő adatbázis-terhelés.
- A térképkártyához szükséges élő attribútumok továbbra is hiánytalanul
  elérhetők; a változás csak az előzményekben történő tárolást érinti.

### Testing

- Új regressziós teszt ellenőrzi, hogy minden élő térképattribútum szerepel a
  Recorderből kizárt attribútumok között.

## 1.0.61 / map card v137 — 2026-07-28

### Fixed

- Mind a 23 támogatott nyelv teljes kártyafordítást kapott: a fő felület,
  a beállítások, a kalibrálás, az állapotok, a parancsok és a hibaüzenetek
  egyik nyelvnél sem esnek vissza hiányzó kulcs miatt angol szövegre.
- A magyar START, STOP és HOME gombfeliratok is magyarul jelennek meg.
- A dekódolt raszteres határvonal szélessége most képernyőpixelben értendő;
  a `boundary_width: 1` valóban egy vékony, egypixeles körvonalat rajzol.
- A tiltott zóna felirata a zóna eredeti középpontján marad, és eltűnik,
  amikor ez a pont kikerül a látható térképről.
- A tiltott zóna felirata csak addig rajzolódik ki, amíg maga a poligon is
  metszi a látható térképet.
- Minden frontendmodul egységes `v137` gyorsítótár-verziót kapott, ezért a
  böngésző nem töltheti vissza a korábbi, képernyőszélhez rögzített feliratot.

### Changed

- A Lovelace-erőforrás gyorsítótár-verziója `v137`.

## 1.0.60 / map card v134 — 2026-07-26

### Added

- A teljes tiltott zónaréteg külön kapcsolóval megjeleníthető vagy elrejthető.
- Az új `show_no_go_zones` YAML-beállítás és a felületi kapcsoló állapota
  oldalfrissítés után is megmarad.
- A tiltott zónák területe és felirata egymástól függetlenül kapcsolható.

### Changed

- A Lovelace-erőforrás gyorsítótár-verziója `v134`.

## 1.0.59 / map card v128 — 2026-07-26

### Fixed

- A YAML-ban megadott `language` elsőbbséget kap a korábban elmentett
  böngészőbeállítással szemben.
- A dekódolt határvonal is használja a `boundary_color` és `boundary_width`
  beállításokat.
- A térkép húzása után nem nyílik meg tévesen a nagy térképnézet.
- A nagy térkép bezárógombja kártyaszerkesztés közben is elérhető marad.
- A tiltott zónák feliratai a látható térképen belül maradnak, és a
  `show_no_go_labels` opcióval kikapcsolhatók.
- Megszűntek a kártyakódban maradt, angol felületen is megjelenő magyar
  szövegek.
- A robot PNG kivágási maszkjából eltűntek a belső átlátszó lyukak.

### Changed

- A Lovelace-erőforrás gyorsítótár-verziója `v128`.

## 1.0.58 / map card v127 — 2026-07-26

### Added

- Felhőkapcsolat-ébresztés és visszaigazolás a robotparancsok előtt.
- Felhő- és robotkapcsolati állapot a térképkártyán.
- Visszajelzés a parancs elküldéséről, végrehajtásáról vagy időtúllépéséről.

### Changed

- Aktív nyírás közben az integráció a gyári Genie alkalmazással azonos
  `req_all_path` parancsot küldi `data: 1` értékkel.
- A friss útvonalfájl letöltése előtt megvárja a `path_time` változását.
- Az útvonal-feltöltési kérés legfeljebb 10 másodpercenként fut.
- A Lovelace-erőforrás gyorsítótár-verziója `v127`.

### Fixed

- A lenyírt terület és az aktuális nyomvonal frissítéséhez már nem kell
  megnyitni a gyári Anthbot alkalmazást.
- A fűnyírási magasság szolgáltatásválasztója szöveges értékeket használ,
  ahogy azt a Home Assistant elvárja.

A v1.0.54 és v1.0.58 közötti részletes változások:
[CHANGELOG_v1.0.58_HU.md](CHANGELOG_v1.0.58_HU.md).

## 1.0.54 / map card v126 — 2026-07-17

### Added

- Anthbot alkalmazás-stílusú történeti útvonal letöltése és MGS v1–v3 dekódolása.
- Nyers, gzip- és zlib-tömörített felhős útvonalfájlok támogatása.
- Útvonalmunkamenetek megőrzése nézetváltás és oldalfrissítés után.
- Állítható szélességű, áttetsző lenyírt terület réteg.
- Új útvonal- és letöltési diagnosztikai attribútumok.
- Teljes telepítő ZIP-et készítő automatikus GitHub Release folyamat.

### Changed

- Aktív nyírás közben az integráció rendszeresen frissíti a történeti útvonalat.
- A felhős és élő útvonal külön rétegen jelenik meg.
- A robot mérete a zoommal együtt változik.
- A Lovelace-erőforrás gyorsítótár-verziója `v126`.

### Fixed

- Távoli vagy hibás útvonalpontok nem kapcsolódnak össze hosszú átlós vonallal.
- Dokkolás és töltés közben a kártya nem rögzít hamis nyírási pontokat.

A v1.0.29 és v1.0.54 közötti részletes összehasonlítás:
[CHANGELOG_v1.0.54_HU.md](CHANGELOG_v1.0.54_HU.md).

## 1.0.29 / map card v101 — 2026-07-16

### Added

- Új lebegő, áttetsző vezérlőmenü, amely mellett a kert térképe folyamatosan látható marad.
- A menü a térkép jobb alsó sarkában lévő gombbal nyitható és zárható.

### Changed

- A vezérlők, beállítások, állapot, diagnosztika és kalibráció egy görgethető üvegpanelen jelennek meg.
- A Lovelace-erőforrás gyorsítótár-verziója `v101`.

## 1.0.28 / map card v100 — 2026-07-15

### Fixed

- Mobilon kétujjas csippentéssel nagyítható és kicsinyíthető a nagy térkép.
- A kétujjas nagyítás a gesztus középpontját követi, és közben a térkép mozgatható is.
- A robot alapmérete nem fix képpontérték, hanem a megjelenített térkép szélességének 5,5%-a.
- A mobilos főnézetben és nagy térképnézetben így azonos marad a robot térképhez viszonyított aránya.
- A `robot_map_ratio` YAML-opcióval az arány egyedileg állítható; az alapérték `0.055`.
- A nagy térkép bezárásakor a zoom és az eltolás visszaáll alaphelyzetbe.
- A `+ / −` gombok nagyítási lépése 15%-ról 30%-ra nőtt.

## 1.0.26 / map card v98 — 2026-07-14

### Fixed

- Lejárt Anthbot bearer tokennél az integráció automatikusan újra bejelentkezik.
- Sikertelen AWS IoT STS-frissítés után új hitelesítéssel ismét lekéri az ideiglenes hozzáférést.
- Az AWS lejárati idő másodperc, ezredmásodperc, számszöveg és ISO dátum formátumban is helyesen értelmezhető.
- Hiányzó lejárati időnél az AWS-adatok legfeljebb 45 percig maradnak gyorsítótárazva.

## 1.0.25 / map card v97 — 2026-07-14

### Fixed

- A nyelvválasztó szövege és lenyíló listája saját sötét megjelenésben ismét jól olvasható.
- A Home Assistant beviteli mezőszíneit csak bekapcsolt „HA téma használata” mellett veszi át.

## 1.0.24 / map card v96 — 2026-07-14

### Added

- Új `theme_background: true` kapcsoló a Felület beállítások fülön.

### Changed

- A kártya alapból ismét a saját eredeti sötét színeit használja.
- A Home Assistant theme színeit csak a „HA téma használata” kapcsoló bekapcsolásakor veszi át.

## 1.0.23 / map card v95 — 2026-07-14

### Fixed

- Üvegháttér mellett a nagy térkép ismét valódi teljes képernyős nézetben nyílik meg.
- Nagy nézetben ideiglenesen kikapcsol a `backdrop-filter`, így nem korlátozza a fix pozicionálást.
- Az üvegháttér és a belső panelek erősebben áttetszőek.

## 1.0.22 / map card v94 — 2026-07-14

### Added

- Új, külön kapcsolható `glass_background: true` üvegháttér-opció a Felület beállítások fülön.

### Changed

- Alapállapotban a háttér ismét normál, nem áttetsző theme-háttér.
- Az üvegháttér és a teljesen átlátszó háttér kölcsönösen kizárja egymást.

## 1.0.21 / map card v93 — 2026-07-14

### Fixed

- Az üveghatás közvetlenül bekerült a kártya Shadow DOM-jába, mert a külső theme `ha-card` CSS-szabályai oda nem jutnak be.
- A kártya és a másodlagos panelek áttetsző témahátteret, elmosást és színtelítést kapnak.

## 1.0.20 / map card v92 — 2026-07-14

### Fixed

- A kártya elsődlegesen a Home Assistant `card-background-color` témahátterét használja a fekete `ha-card-background` helyett.
- A `transparent_background` most már az egész kártyát átlátszóvá teszi, beleértve a fejlécet, a paneleket és a kalibrációs részt is.

## 1.0.19 / map card v91 — 2026-07-14

### Changed

- A kártya háttere, szövegei, panelei, elválasztói, kiemelőszíne, lekerekítése és árnyéka követi az aktív Home Assistant témát.
- A Start, Stop és Töltő műveleti gombok saját állapotszínei megmaradnak.

## 1.0.18 / map card v90 — 2026-07-14

### Fixed

- Három egymást követő átmeneti cloud hiba alatt megmarad az utolsó érvényes állapot.
- Az indítási parancsok között késleltetés van, így nem írják felül egymást az AWS shadow-ban.
- Az integráció ellenőrzi a tényleges nyírási állapotot, és sikertelen indulásnál egyszer újrapróbálja.

## 1.0.17 / map card v89 — 2026-07-14

### Changed

- A Beállítások külön „Robot beállítások” és „Felület beállítások” fülre vált szét.
- A `map_only` és `transparent_background` kapcsolható a felületről, és böngészőnként megmarad.
- Csak térkép módban dupla kattintással vagy dupla koppintással visszaállítható a teljes kezelőfelület.

## 1.0.16 / map card v88 — 2026-07-14

### Added

- `transparent_background: true` opció floorplan rétegként történő megjelenítéshez.
- Átlátszó módban a háttérkép és az alap kitöltés eltűnik, de a geometriai illesztés változatlan marad.

## 1.0.15 / map card v87 — 2026-07-14

### Added

- `map_only: true` mód, amely kizárólag a térképet jeleníti meg floorplan használathoz.
- Gombonként beállítható `button_actions`, tetszőleges Home Assistant service vagy script meghívásával.

## 1.0.14 / map card v86 — 2026-07-14

### Changed

- A térkép magassága automatikusan követi a háttérkép valódi oldalarányát.
- A kártya átméretezésekor a háttérkép és a vászon együtt méreteződik.
- A kézi `height` beállítás továbbra is felülbírálja az automatikus méretezést.

## 1.0.13 / map card v85 — 2026-07-13

### Removed

- A nem támogatott no-go szegélynyírás és a hozzá tartozó pontgenerálás.
- A „Minden szegély” művelet, mert az a hibás no-go feladatot is elindította.

### Unchanged

- A gyári külső szegélynyírás és a töltőállomás körüli nyírás továbbra is elérhető.

## 1.0.12 / map card v84 — 2026-07-13

### Fixed

- A generált no-go pontokat nem egy nagy, firmware által elutasítható listában küldi.
- Minden pont külön `region_mow_start` feladatként indul.
- A következő pont csak az előző pontnyírás befejezése után kerül elküldésre.

## 1.0.11 / map card v83 — 2026-07-13

### Fixed

- A `nest_mow_start` helyesen töltő körüli nyírásként jelenik meg.
- A no-go szegélynyírás már nem indít töltő körüli feladatot.

### Added

- A felhőből lekért tényleges no-go határpontok követése.
- Az eredeti alakzattal párhuzamos, alapértelmezetten 30 cm-rel kifelé eltolt útvonal.
- Állítható biztonsági távolság és pontsűrűség a Home Assistant szolgáltatásban.

## 1.0.10 / map card v82 — 2026-07-13

### Added

- Külső szegélyvágás külön Home Assistant szolgáltatással és kártyagombbal.
- No-go zónák körbevágása a gyári `nest_mow_start` paranccsal.
- Minden szegély vágása egyetlen kártyagombbal.
- Külön Home Assistant gombentitások mindhárom szegélyvágási módhoz.

## 1.0.9 / map card v81 — 2026-07-13

- Az „Utolsó frissítés” időpontja a Home Assistant beállított helyi időzónájában jelenik meg.
- Ha nincs HA-időzóna, a böngésző helyi időzónája az alapértelmezés.
- A dátum és idő formátuma követi a kártyán kiválasztott nyelvet.

## 1.0.8 / map card v80 — 2026-07-12

### Added

- Turkish, Thai, Vietnamese, Korean, and Khmer translations.
- Automatic language detection for all five new languages.

## 1.0.7 / map card v79 — 2026-07-12

### Fixed

- Keep the language selector and other settings controls open while live mower
  data refreshes in the background.

## 1.0.6 / map card v78 — 2026-07-12

### Added

- Automatic Home Assistant language detection.
- Manual language selector in the card settings.
- 18 selectable languages, including simplified and traditional Chinese.
- English fallback for missing translations.

### Changed

- Map labels, controls, status values, settings, diagnostics, and calibration
  controls now use the card translation system.

## 1.0.5 / map card v77 — 2026-07-12

### Added

- Photo-backed Anthbot map card for Home Assistant.
- Live robot position, mowing trail, zones, no-go areas, charger, and controls.
- Full-screen map mode with zoom, pan, calibration, and YAML export.
- Visible position and heading badges in the upper-left corner.
- Correct heading conversion matching the official app: `pose.yaw` is stored
  in milliradians and converted with `yaw * 180 / (pi * 1000)`.
- HACS metadata and public installation documentation.

### Changed

- Repository links and code owner now point to `Mqbretrofit/ha-anthbot-map-v2`.
- Removed embedded vendor AWS keys; IoT access now requires temporary STS
  credentials returned by the Anthbot cloud.

## Earlier integration work

The integration is based on the upstream projects listed in [NOTICE.md](NOTICE.md).
See their histories for changes made before this combined map release.
# 2.2.1-beta.48

- Added the app-style visual edge overlap editor to Anthbot Map Card.
- The mower edge now follows the selected 5–20 cm boundary overhang with a matching measurement arrow.
- Empty or deleted `ridable_areas` entries without vertices are hidden from the settings UI.
- Added all 23 supported translations for the edge editor.

# 2.2.1-beta.47

- Download the app's separate `ridable_area` map file using
  `ridable_area_time` and expose its editable edges to the map cards.
- Expose `ridable_area_error` for direct Home Assistant diagnostics.

# 2.2.1-beta.46

- Added the app-compatible `set_edge_settings` service.
- Edge overlap now uses the mobile app's `ride_distance` field and
  `ridable_area_set` full-list payload.
- Supported overlap values: 5, 7, 10, 13, 15, 17 and 20 cm.
