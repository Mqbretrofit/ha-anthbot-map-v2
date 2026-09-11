# Anthbot Map Home Assistanthoz

[English](README.md) | Magyar

[![Kiadás](https://img.shields.io/badge/release-v2.4.6.4-blue)](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.6.4)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Megnyitás HACS-ban](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mqbretrofit&repository=ha-anthbot-map-v2&category=integration)
[![Licenc: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Támogatás](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-EA4AAA?logo=githubsponsors)](https://github.com/sponsors/Mqbretrofit)

Nem hivatalos Home Assistant-integráció és egyedi térképkártya ANTHBOT robotfűnyírókhoz.

Az Anthbot Map összekapcsolja a Home Assistantot az ANTHBOT felhővel, modellenként kezeli a robotokat, és tartalmazza az `anthbot-map-card` Lovelace-kártyát. Vezérlést, térkép-/útvonal-/zónakezelést, nyírási előzményeket, diagnosztikát, Battery Saver funkciókat és külön Genie / M-széria / N8 működési ágakat biztosít.

> [!WARNING]
> Ez egy független közösségi projekt, amely nem áll kapcsolatban az ANTHBOT gyártójával és nem hivatalos ANTHBOT-termék.

## Aktuális verzió

Stabil verzió: **2.4.6.4**

Legfrissebb kiadás: [Anthbot Map v2.4.6.4](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.6.4)

### A 2.4.6.4 legfontosabb változásai

- Az automatikus diagnosztika esemény-élre működik, így ugyanaz a tartós diagnosztikai állapot nem kerül óránként újra elküldésre.
- Induláskor a már fennálló diagnosztikai állapot kiindulási állapotként kerül felvételre, ezért egy régi esemény nem generál új riportot pusztán újraindítás miatt.
- A korábbi cloud task-event hibák megmaradnak előzményként, de friss/elavult jelölést kapnak, és lejárat után önmagukban már nem indítanak automatikus hibariportot.
- Az AWS IoT live-shadow figyelő váratlan futásidejű vagy transport hibák után sem áll le végleg.
- Többszöri sikertelen reconnect után a kliens új ideiglenes IoT hitelesítőt kérhet és korlátozott reconnect-kísérletekkel tovább működik.
- Az M-szériás térképnél külön kezeljük a logikai `map.map_id`, `area_id`, `plan_id` és a `map_manager_<serial>.tar.gz` belsejében található raster `map_id` értékeket.
- Az eltérő logikai és raster map ID többé nem okoz felesleges map-manager újraletöltést.
- Az M-szériás térképjavítás M5/M9 családra korlátozott; az N8 vezérlési útvonalát nem bővíti és nem módosítja.

### 2.4.6.x riportolás és fejlesztői diagnosztika

A 2.4.6 sorozatban bekerült és tovább fejlődött az opcionális projektdiagnosztika:

- külön kapcsolható anonim használati statisztika a telepítések/modellek/verziók áttekintéséhez;
- külön kapcsolható automatikus diagnosztikai riport az újonnan aktív robot- és cloud task-event hibákhoz;
- anonim statisztika engedélyezése esetén könnyű verzió-heartbeat induláskor/újratöltéskor;
- külön **Csak olvasási fejlesztői lekérések engedélyezése** jogosultság az **Anthbot Map -> Beállítások -> Fejlesztés és diagnosztika** alatt;
- opt-in read-only Developer Agent eszközök: `full_state`, `full_diagnostics`, `state_inspector`, `state_diff`, `refresh_diagnostics`;
- szigorúan csak olvasási működés: nincs tetszőleges Python-, URL-, HTTP-, MQTT-, metódus-/property-futtatás és nincs robotvezérlő parancs a Developer Agentből.

Az anonim statisztika, az automatikus diagnosztika és a read-only fejlesztői hozzáférés három külön jogosultság. A normál robotműködéshez egyik sem kötelező.

### N8 támogatás

Az N8-specifikus vezérlés, állapotkezelés, térkép-/útvonalkezelés és modellspecifikus entitások bekerültek, és tesztelésre elérhetők.

- **Code/API validáció:** elkészült külön regressziós és modellszeparációs tesztekkel.
- **Valós N8 hardveres validáció:** ebben a projektben még nem történt meg.
- A Genie és M-szériás modellrouting továbbra is elkülönül az N8-tól.

N8 tulajdonosok tesztjeit és modellspecifikus visszajelzéseit várjuk.

## Támogatott modellek

- **ANTHBOT Genie:** támogatott és közvetlenül hardveren tesztelt.
- **ANTHBOT M9 Pro:** M-szériás vezérlés, állapot, térkép, útvonal, zóna és előzménykezelés támogatott és közvetlenül hardveren tesztelt.
- **ANTHBOT M9:** támogatott a közös M-szériás implementáción keresztül; közvetlen hardverteszt még nem történt.
- **ANTHBOT M5:** támogatott a közös M-szériás implementáción keresztül; közvetlen hardverteszt még nem történt.
- **ANTHBOT N8:** az implementáció bekerült és tesztelhető; code/API szinten ellenőrzött, de valós N8 hardveres validáció még nincs.

## Fő funkciók

- ANTHBOT felhős bejelentkezés a Home Assistant felületéről
- több robot egy ANTHBOT-fiókban
- tartós AWS IoT/MQTT live-shadow kapcsolat reconnect-felügyelettel
- natív Home Assistant `lawn_mower` entitás
- teljes terület-, zóna-, külső szegély- és töltőkörüli nyírás, ahol az adott modell támogatja
- szüneteltetés, folytatás, leállítás és dokkhoz visszatérés
- külön Genie / M-széria / N8 modellrouting
- akkumulátor-, töltés-, státusz-, RTK-, hálózat-, firmware-, karbantartási-, hiba- és diagnosztikai adatok
- térkép, gyep-határvonal, zónák, tiltott zónák, robotpozíció, élő útvonal és nyírási lefedettség
- korábbi nyírási feladatok elérhető terület-, térkép-, útvonal-, időtartam- és zónaadatai
- opcionális légi/drónfotó háttérként
- teljes képernyős térkép, zoom, mozgatás és forgatás
- külön térkép-, robot-, nyírásiútvonal- és dekódolthatárvonal-kalibráció
- modellenkénti robotképek
- robotonkénti egyéni kártyagomb-műveletek
- Battery Saver profilok, töltési határértékek, közös/külön RTK-tápkezelés és újraindítás után is megmaradó állapot
- ismétlődő 55+1 perces Shutdown Guard támogatott okoskonnektoros töltővezérléshez
- eső miatti várakozás és cloud task-event diagnosztika
- opcionális anonim statisztika, automatikus diagnosztika és read-only Developer Agent
- 23 választható felületi nyelv

## Más ANTHBOT-integráció használata

Az Anthbot Map v2 saját `anthbot_map` integrációs domaint használ, ezért egy korábbi ANTHBOT-integráció mellett is telepítve maradhat. Ugyanahhoz a robothoz két integráció ne legyen egyszerre engedélyezve.

> [!CAUTION]
> Ne futtasd egyszerre az Anthbot Map integrációt a `vincentjanv/anthbot_genie_ha`, az AdrianTIonut fork vagy más ANTHBOT Home Assistant-integráció mellett ugyanarra a robotra. A párhuzamos integrációk egymással versengő felhőkapcsolatokat és ütköző parancsokat okozhatnak.

Biztonságos átváltás és visszaállítás:

1. Hagyd telepítve a korábbi integrációt.
2. Tiltsd le a konfigurációs bejegyzését a **Beállítások -> Eszközök és szolgáltatások** oldalon.
3. Indítsd újra a Home Assistantot.
4. Add hozzá és teszteld az **Anthbot Map** integrációt.
5. Visszaállításhoz tiltsd le az Anthbot Map-et, engedélyezd a korábbi integrációt, majd indítsd újra a Home Assistantot.

A meglévő entity registry bejegyzések miatt az új entity ID-k `_2`, `_3` vagy későbbi utótagot kaphatnak. Ez nem hiba.

## Követelmények

- Home Assistant 2024.1.0 vagy újabb
- HACS az ajánlott telepítési módhoz
- működő ANTHBOT-fiók
- internetkapcsolat az ANTHBOT felhőhöz

# Telepítés

## Telepítés HACS-ból

1. Nyisd meg a **HACS -> Integrations** oldalt.
2. A hárompontos menüben válaszd a **Custom repositories** lehetőséget.
3. Add hozzá:

   ```text
   https://github.com/Mqbretrofit/ha-anthbot-map-v2
   ```

4. Típus: **Integration**.
5. Telepítsd az **Anthbot Map** integrációt.
6. Indítsd újra a Home Assistantot.
7. Nyisd meg a **Beállítások -> Eszközök és szolgáltatások -> Integráció hozzáadása** oldalt, és keresd meg az **Anthbot Map** integrációt.

Az `anthbot-map-card` az integráció része, ezért nem kell külön HACS dashboard repository.

## Kézi telepítés

1. Töltsd le a ZIP-et a legfrissebb GitHub kiadásból.
2. Másold a `custom_components/anthbot_map/` mappát a `/config/custom_components/anthbot_map/` helyre.
3. Indítsd újra a Home Assistantot.
4. Add hozzá az **Anthbot Map** integrációt a **Beállítások -> Eszközök és szolgáltatások** oldalon.

## Lovelace resource

Lovelace storage módban az integráció automatikusan létrehozza vagy frissíti ezt:

```text
/anthbot-map-v2/anthbot-map-card.js
```

Típus: **JavaScript module**.

Ha kézzel kell felvenni, ezt használd:

```text
/anthbot-map-v2/anthbot-map-card.js?v=2.4.6.4
```

Egyszerre csak egy Anthbot Map Card resource legyen engedélyezve.

# Térképkártya hozzáadása

## Minimális konfiguráció

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
```

A `sensor.YOUR_MOWER_map` helyére az integráció által létrehozott tényleges map entitás kerüljön.

## Opcionális kertfotó

Másolj egy felülnézeti képet a `/config/www/garden.jpg` helyre, majd add meg:

```yaml
image: /local/garden.jpg
```

A minimális perspektívatorzítású felülnézeti légi vagy drónfotó adja a legjobb kalibrációs eredményt.

## Ajánlott kalibrációs blokkok

```yaml
calibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
robotCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
mowingPathCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
decodedBoundaryCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

Ajánlott sorrend: alap térképigazítás, nyírási útvonal igazítása, robot kalibrációja, majd a dekódolt határvonal igazítása.

## Robot iránya

Ajánlott beállítás:

```yaml
robot_heading_source: cloud
```

Lehetséges módok:

- `cloud`: a gyári app működéséhez igazodó cloud `pose.yaw`; ajánlott
- `movement`: irányszámítás az egymást követő pozíciókból
- `auto`: elsődlegesen movement, szükség esetén cloud fallback

# Battery Saver

A Battery Saver Home Assistant `switch` entitással tudja vezérelni a töltő tápját. A kiválasztott profiltól/beállításoktól függően kezelheti a felső töltési szintet, nyugalmi fenntartó töltést, félbehagyott feladat folytatási küszöbét, közös/külön RTK-tápot és az ismétlődő 55+1 perces Shutdown Guardot.

A Battery Saver állapota robotonként tartósan mentett, ezért a Home Assistant újraindítása nem nullázza az aktív akkukezelési ciklust.

> [!IMPORTANT]
> A töltőtáp automatizálásához megfelelően konfigurált Home Assistant `switch` entitás szükséges. Az automatikus használat előtt ellenőrizd a teljes beállítást.

# Fejlesztés és diagnosztika

Az opcionális projekt-riportolási engedélyeket az **Anthbot Map -> Beállítások -> Fejlesztés és diagnosztika** oldalon lehet kezelni.

A jogosultságok egymástól függetlenek:

- **Anonim használati statisztika megosztása**
- **Automatikus diagnosztika**
- **Csak olvasási fejlesztői lekérések engedélyezése**

A normál robotvezérléshez egyik sem szükséges.

A riportolás célja a valós modellen/API-n jelentkező problémák feltárása úgy, hogy a robotvezérlési útvonal elkülönítve maradjon. A Developer Agent csak az integrációba előre beépített biztonságos read-only probe-okat használhatja.

# Nyírási előzmények

Nyisd meg az Anthbot Map kártyát, válaszd a **Diagnosztika**, majd a **Korábbi nyírási feladatok** részt. A befejezett munkákhoz elérhető lehet dátum, időtartam, lenyírt terület, százalék, nyírási mód, indítás oka, érintett zónák és korábbi térkép-/útvonaladat.

# Frissítés

HACS használatakor:

1. Telepítsd a HACS által felajánlott frissítést.
2. Indítsd újra a Home Assistantot.
3. Frissítsd keményen a böngészőt `Ctrl+Shift+R` billentyűvel.

YAML resource módban a cache-busting verziót is állítsd az aktuális verzióra, például:

```text
/anthbot-map-v2/anthbot-map-card.js?v=2.4.6.4
```

# Hibakeresés

## A kártya nem található

Ellenőrizd, hogy:

- az Anthbot Map telepítve van és a Home Assistant újra lett indítva;
- létezik a `/config/www/anthbot-map-v2/anthbot-map-card.js`;
- az `/anthbot-map-v2/anthbot-map-card.js` JavaScript module-ként szerepel;
- nincs engedélyezve régi, duplikált Anthbot Map Card resource.

Ezután `Ctrl+Shift+R`.

## Nem jelenik meg a térkép

Ellenőrizd, hogy a megfelelő robot map entitása van kiválasztva, annak állapota ready, és az attribútumokban van aktuális robot-/térképadat. Nézd meg a Home Assistant naplóban az `anthbot_map` hibákat is.

## N8 probléma

Az N8 támogatás jelenleg tesztelésre elérhető, de ebben a projektben még nem történt valós N8 hardveres validáció. N8-specifikus hiba jelentésekor csatolj személyes adatoktól megtisztított diagnosztikát.

# Hibák jelentése

Issue nyitása:

https://github.com/Mqbretrofit/ha-anthbot-map-v2/issues

Diagnosztika közzététele előtt távolítsd el a jelszavakat, bearer tokeneket, AWS ID-kat/kulcsokat, PIN-kódokat, GPS-koordinátákat, kertfotókat és egyéb személyes adatokat.

# A fejlesztés támogatása

Az Anthbot Map fejlesztése protokollkutatást, modellenkénti fejlesztést, valódi eszközös tesztelést, diagnosztikát és folyamatos kompatibilitási munkát igényel.

Ha hasznos számodra a projekt, GitHub Sponsorson támogathatod a további fejlesztést:

**https://github.com/sponsors/Mqbretrofit**

Havi és egyszeri támogatás is választható. Konkrét modell vagy funkció fejlesztése a repository **Sponsored feature request** issue űrlapján is javasolható.

További információ: [SUPPORT.md](SUPPORT.md)

A támogatás ezt a független, nyílt forráskódú projektet segíti. Nem jelent beleszólási jogot a roadmapbe, és nem garantálja, hogy egy kért funkció technikailag megvalósítható.

# Köszönet

- https://github.com/vincentjanv/anthbot_genie_ha
- https://github.com/AdrianTIonut/anthbot_genie_ha
- https://github.com/reloxx13/ioBroker.anthbot-genie

# Korábbi részletes dokumentáció

A korábbi 2.4.5 magyar README változatlanul megőrzésre kerül a `docs/archive/README_HU_v2.4.5.md` fájlban. Az aktuális működéshez és verzióhoz ezt a README-t és a legfrissebb release note-okat kell alapul venni.

# Licenc

MIT - lásd [LICENSE](LICENSE).
