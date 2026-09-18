# Anthbot Map Home Assistanthoz

[English](README.md) | Magyar

[![Kiadás](https://img.shields.io/badge/release-v2.4.8.0-blue)](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.8.0)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Megnyitás HACS-ban](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mqbretrofit&repository=ha-anthbot-map-v2&category=integration)
[![Licenc: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Támogatás](https://img.shields.io/badge/Sponsor-GitHub%20Sponsors-EA4AAA?logo=githubsponsors)](https://github.com/sponsors/Mqbretrofit)

Nem hivatalos Home Assistant-integráció és egyedi térképkártya ANTHBOT robotfűnyírókhoz.

Az Anthbot Map összekapcsolja a Home Assistantot az ANTHBOT felhővel, modellenként kezeli a robotokat, és tartalmazza az `anthbot-map-card` Lovelace-kártyát. Vezérlést, térkép-/útvonal-/zónakezelést, nyírási előzményeket, diagnosztikát, Battery Saver funkciókat és külön Genie / M-széria / N8 működési ágakat biztosít.

> [!WARNING]
> Ez egy független közösségi projekt, amely nem áll kapcsolatban az ANTHBOT gyártójával és nem hivatalos ANTHBOT-termék.

## Aktuális verzió

Stabil verzió: **2.4.8.0**

Legfrissebb kiadás: [Anthbot Map v2.4.8.0](https://github.com/Mqbretrofit/ha-anthbot-map-v2/releases/tag/v2.4.8.0)

### A 2.4.8.1 legfontosabb változásai

- Javítja a natív ANTHBOT app-ütemezés visszaírását az M5/M9/N8/Pion modellcsaládnál.
- A pontos M-szériás `appointment` / `delete_appointment` payloadot használja, és létrehozza a szükséges következő numerikus szabályazonosítót.
- A már működő Genie ütemezési útvonal változatlan maradt.
- Valódi M9 Pro roboton ellenőrizve: a kártyáról létrehozott ütemezés most már megjelenik az ANTHBOT appban.
- A teljes kiadás előtti validáció **365/365 sikeres unit teszttel** zárult.

### A 2.4.8.0 legfontosabb változásai

- A robot natív ANTHBOT appos ütemezése az egyetlen hiteles forrás; ezt tükrözi a HA-naptár és az Anthbot Map Card.
- A kártyáról létrehozhatók, szerkeszthetők és törölhetők a natív heti app-szabályok, a modell- és firmware-specifikus mezők megőrzésével.
- Időzített **nyírj eddig** és **maradj bent eddig** felülírás, valamint felülírástörlés került a kártyába.
- Robothoz kötött `next_mow`, natív HA robot-/ütemezési események, opcionális időjárásos halasztás és korlátozott pótlási időablak került be.
- Heti szabályonként beállítható zóna és vágási magasság; a kikapcsolt app-szabály látható marad, de nem hoz létre következő nyírási időpontot.
- A valódi következő nyírás kéken jelenik meg a térkép lebegő állapotkijelzőjében, de csak akkor, ha ténylegesen létezik.
- A Genie 1000 natív app-ütemezésének betöltése valódi roboton ellenőrizve; a kiadás előtti teljes validáció **363/363 sikeres unit teszttel** zárult.

### A 2.4.7.3 legfontosabb változásai

- Javult az élő térkép teljesítménye: a rövid időn belül érkező coordinator frissítések a WebSocket publikálás előtt összevonódnak.
- A live-map snapshot és delta felépítése kikerült a Home Assistant event loopból; a módosítható path adatok frame-készítés előtt külön másolatot kapnak, így a közben növekvő útvonal nem tud hibás, szétszakadt frissítést okozni.
- Megmaradt a reconnect/full-snapshot folytonosság, a sequence/resync védelem, a gördülő path-ablak és az abszolút indexes élő útvonalkezelés.
- Bekerült a tesztelt 2.4.7.2 performance ágból a legfrissebb Genie live-path és nyírási százalék megjelenítési hardening, az M-szériás progress post-trim kezelés, az álló helyzet pozíciókezelése és a location-recorder hardening.
- Megmaradt a 2.4.7.2 startup-safe Developer Agent életciklus és a cloud/API resilience javítások.
- A production robotvezérlési routing nem változott; az M-szériás ellenőrzött `stop_all_tasks` payload is változatlan maradt, csak az elavult regressziós tesztelvárások lettek frissítve.
- Teljes kiadás előtti validáció: **359/359 unit teszt sikeres**, továbbá Python fordítási és célzott live-map ellenőrzések is lefutottak.
- A release dokumentáció egységesen a `CHANGELOG.md` fájlban folytatódik; a korábban publikált részletes kiadási jegyzetek a GitHub Releases alatt továbbra is elérhetők.

### A 2.4.7.0 legfontosabb változásai

- A nagy frekvenciájú live map/path/pose adatfolyam levált a Home Assistant entity state mechanizmusáról, és külön WebSocket transporton jut el a kártyához.
- Első csatlakozáskor teljes snapshot érkezik, utána csak path delták mennek sequence-követéssel, automatikus resync-kel, path-id váltáskezeléssel és hosszú útvonalakhoz gördülő path-ablakkal.
- Live-stream módban a Map entitás kompakt marad: a teljes `path`, `cloud_path`, `mowed_path` és `pose` geometria nem kerül a Home Assistant state-be vagy a Recorderbe.
- A kártya régi periodikus Map-entity pollingja live-stream módban leáll; releváns kompakt állapotváltozás nélkül a Recorder-terhelés nagyjából percenként egy heartbeat írásra csökken.
- A drága No-Go geometriai ellenőrzés kikerült a Home Assistant event loopból az M-szérián, az N8-on és a Genie path diagnosztikánál is; stabil revision cache és korlátozott live ellenőrzési gyakoriság védi a rendszert.
- A robotvezérlési command routing nem változott: a Genie, az M5/M9 család és az N8 vezérlési útvonalai továbbra is külön maradnak.
- Valódi ANTHBOT M9 Pro roboton, aktív nyírás közben ellenőrizve lett a WebSocket útvonal, a Recorder-terhelés csökkenése, a Home Assistant restart, a reconnect és a teljes snapshot visszatöltése.

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

Az N8-specifikus vezérlés, állapotkezelés, térkép-/útvonalkezelés és modellspecifikus entitások bekerültek.

- **Code/API validáció:** elkészült külön regressziós és modellszeparációs tesztekkel.
- **2.4.7.3 stabilitási védelem:** az N8 is a védett No-Go executor útvonalat és külön regressziós teszteket használja, a jelenlegi live-map transport pedig megtartja a modellenkénti elkülönítést.
- **Valós N8 hardveres validáció:** ebben a projektben még nem történt meg közvetlenül.
- A Genie és M-szériás modellrouting továbbra is elkülönül az N8-tól.

N8 tulajdonosok tesztjeit és modellspecifikus visszajelzéseit várjuk.

## Támogatott modellek

- **ANTHBOT Genie:** támogatott és közvetlenül hardveren tesztelt; a Genie path diagnosztika elkülönül a többi modelltől.
- **ANTHBOT M9 Pro:** M-szériás vezérlés, állapot, térkép, útvonal, zóna és előzménykezelés támogatott és közvetlenül hardveren tesztelt, beleértve a 2.4.7.3 live-stream/Recorder architektúrát és az azt követő performance hardeninget is.
- **ANTHBOT M9:** támogatott a közös M-szériás implementáción keresztül; közvetlen hardverteszt még nem történt.
- **ANTHBOT M5:** támogatott a közös M-szériás implementáción keresztül; közvetlen hardverteszt még nem történt.
- **ANTHBOT N8:** külön N8 implementációval támogatott; code/API és regressziós szinten ellenőrzött, de közvetlen 2.4.7.3 hardveres terepi validáció még nincs.

## Fő funkciók

- ANTHBOT felhős bejelentkezés a Home Assistant felületéről
- több robot egy ANTHBOT-fiókban
- tartós AWS IoT/MQTT live-shadow kapcsolat reconnect-felügyelettel
- külön WebSocket live-map transport snapshot, delta, sequence és automatikus resync kezeléssel
- kompakt Map entitás, amely live-stream módban nem írja a nagy frekvenciájú teljes geometriát a Home Assistant state-be és Recorderbe
- natív Home Assistant `lawn_mower` entitás
- a natív ANTHBOT app-ütemezés tükrözése a HA-naptárba és a kártyára, visszaírásos szerkesztéssel
- időzített nyírás/parkolás felülírás és robothoz kötött következő tényleges nyírás szenzor
- szabályonkénti zónák, vágási magasság, valamint opcionális időjárás-előrejelzés és pótlás
- natív robot-életciklus- és ütemezési események HA automatizálásokhoz
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

Az ütemezés beállítása és példái: [Home Assistant scheduling and overrides](docs/HA_SCHEDULING.md).

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
/anthbot-map-v2/anthbot-map-card.js?v=2.4.7.3
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
/anthbot-map-v2/anthbot-map-card.js?v=2.4.7.3
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

Ellenőrizd, hogy a megfelelő robot Map entitása van kiválasztva, és annak állapota `ready`. Normál 2.4.7.3 live-stream módban a teljes élő `path`/`pose` geometria szándékosan **nincs** a Map entitás attribútumaiban. Helyette az entitásban `live_stream_available: true` és `live_stream_transport: websocket` várható, a kártya pedig Home Assistant WebSocketen kapja a teljes snapshotot és az élő deltákat.

Ha a térkép továbbra sem jelenik meg, frissítsd keményen a böngészőt, ellenőrizd, hogy csak egy Anthbot Map frontend resource aktív, és nézd meg a Home Assistant naplójában az `anthbot_map` vagy WebSocket hibákat.

## N8 probléma

Az N8 támogatás bekerült és code/API szinten ellenőrzött, de a 2.4.7.3 közvetlen N8 hardveres terepi validációja ebben a projektben még nem történt meg. N8-specifikus hiba jelentésekor csatolj személyes adatoktól megtisztított diagnosztikát.

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
