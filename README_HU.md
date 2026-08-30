# Anthbot Map Home Assistanthoz

[English](README.md) | Magyar

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Mqbretrofit&repository=ha-anthbot-map-v2&category=integration)
[![Licenc: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Nem hivatalos Home Assistant-integráció és egyedi térképkártya ANTHBOT
robotfűnyírókhoz.

Az integráció összekapcsolja a Home Assistantot az ANTHBOT felhővel, létrehozza
a robot vezérléséhez és állapotának megjelenítéséhez szükséges entitásokat,
valamint tartalmazza az `anthbot-map-card` Lovelace-kártyát is.

A kártyán megjeleníthető a robot, a töltőállomás, a gyep határvonala, a nyírási
és tiltott zónák, az aktuális és korábbi nyírási útvonalak, a lenyírt terület,
valamint egy saját légi vagy drónfelvétel a kertről.

> [!WARNING]
> Ez egy közösségi fejlesztés, amely nem áll kapcsolatban az ANTHBOT gyártójával.

## Aktuális verzió

Stabil verzió: **2.4.2**

### A 2.4.2 legfontosabb változásai

- Bekerültek a robotonként, Home Assistantban mentett egyéni
  kártyagomb-műveletek; a korábbi YAML `button_actions` beállítás továbbra is
  használható.
- Másik töltő-okoskonnektor kiválasztásakor az 55+1 perces anti-shutdown
  védelem azonnal az új konnektorhoz igazodik.
- A százalékok egyszerű módosítása nem indítja újra a futó időzítést, a hibás
  régi értékeket pedig biztonságosan korrigálja.
- Minden meglévő profil, fordítás, vezérlés, RTK-kezelés és újraindítás utáni
  állapotmentés változatlanul megmaradt.

### A 2.4.1 legfontosabb változásai

- Három kész akkukímélő profil került be: **Max. akkukímélés**,
  **Kiegyensúlyozott** és **Mindig indulásra kész**, valamint megmaradt a
  teljesen állítható **Egyéni** profil.
- Robotenként tartósan menti a felső töltési határt, a fenntartó töltés
  indítási szintjét, a félbehagyott feladat folytatási szintjét, a közös
  RTK-táp beállítását, az aktuális működési fázist és a shutdown-védelem
  időzítését. A Home Assistant újraindítása már nem indítja újra az aktív
  akkukímélő ciklust.
- Bekerült az **55+1 perces anti-shutdown védelem**: dokkolt, készenléti
  robotnál, kikapcsolt töltőtáp esetén 55 perc után egy percre bekapcsolja a
  töltőt, majd újrakezdi a ciklust.
- A kártyán látható a shutdown-védelem állapota és a következő impulzusig
  hátralévő idő, beleértve az inicializálást és az aktív ébresztő töltést.
- A normál fenntartó töltés különválik a rövid ébresztő impulzustól, és hiányzó
  robot-telemetria esetén a rendszer nem kapcsolja le vakon a tápot.
- Helyesen kezeli a közös és a külön RTK-tápot nyírás, dokkhoz visszatérés,
  töltés és RTK-inicializálás közben.
- Az akkumulátorkímélő mód kikapcsolásakor azonnal visszakapcsolja a töltőtápot,
  a kézzel elindított töltést pedig nem téveszti össze automatikus
  akkukímélő-váltással.
- Javult az integráció leállítása és újratöltése; a mentett beállítások Home
  Assistant-újraindítás nélkül, azonnal életbe lépnek.
- Az akkukímélő csempe csak a beállítóablakot nyitja meg; a nagyobb be- és
  kikapcsoló jelölőnégyzet a popupban marad.
- Az új akkukímélő felület mind a 23 támogatott nyelven elérhető.

### A 2.4.0 legfontosabb változásai

- Megjelent az opcionális akkumulátorkímélő mód Home Assistant `switch`
  entitással vezérelt töltőkhöz.
- Külön beállítható a felső töltési határ, a nyugalmi fenntartó töltés alsó
  szintje és a megszakított feladat folytatási töltöttsége.
- Az alacsony töltöttség miatti visszatérést az ANTHBOT felhő `1021`
  feladateseménye jelzi; élő nyírási százalékot a felhő nem szolgáltat, ezért
  az integráció nem becsül hamis értéket.
- A Home Assistantból indított teljes, zóna-, szegély- és töltőkörüli nyírás
  megjegyezhető és a helyreállító töltés után folytatható.
- A töltő automatikus bekapcsolásakor a robot ideiglenesen elnémul, majd
  visszakapja a korábbi hangerőt.
- Új feladatesemény-szenzorok és diagnosztikai adatok készültek.

### A 2.3.0 legfontosabb változásai

- Megjelentek a korábbi nyírási feladatok és a hozzájuk elérhető terület-,
  térkép- és útvonaladatok.
- Külön kalibrálható a térkép, a robot, a nyírási útvonal és a dekódolt
  határvonal.
- Javítva lett a robot vízszintes mozgásakor hibásan tükrözött haladási irány.
- Javítva lett a nyírási útvonal forgatása nem négyzetes térképeken.
- Javult a több robotot tartalmazó ANTHBOT-fiókok kezelése.
- Elkészült a kalibráció és a nyírási előzmények fordítása mind a 23 támogatott
  nyelvre.
- Kikerültek a megmaradt frontend debug üzenetek.
- Megjelent az M5/M9 modellek kísérleti shadow- és élőútvonal-kezelése.

> [!IMPORTANT]
> **Az ANTHBOT M5 és M9 modelleknél a térképes megjelenítés jelenleg még nem
> működik.** Az M5/M9 támogatás kísérleti, ezért az elérhető állapotok és
> funkciók modellenként és firmware-verziónként eltérhetnek.

## Támogatott modellek

Az integráció elsősorban az ANTHBOT Genie sorozattal lett tesztelve.

- ANTHBOT Genie: elsődlegesen támogatott
- ANTHBOT M5/M9: kísérleti támogatás
- M5/M9 térképes megjelenítés: jelenleg nem működik

## Más ANTHBOT-integráció használata

Az Anthbot Map v2 saját `anthbot_map` integrációs domaint használ, ezért egy
korábbi ANTHBOT-integráció mellett is telepítve maradhat. A két integráció
azonban ne legyen egyszerre engedélyezve.

> [!CAUTION]
> Ne futtasd egyszerre az Anthbot Map integrációt a
> `vincentjanv/anthbot_genie_ha`, az AdrianTIonut fork vagy más ANTHBOT Home
> Assistant-integráció mellett. Az egyidejű működés több felhőkapcsolatot
> nyithat, és egymással ütköző parancsokat küldhet ugyanannak a robotnak.

Biztonságos átváltás és visszaállítás:

1. Hagyd telepítve a korábbi integrációt.
2. Tiltsd le a konfigurációs bejegyzését a **Beállítások -> Eszközök és
   szolgáltatások** oldalon.
3. Indítsd újra a Home Assistantot.
4. Add hozzá és teszteld az **Anthbot Map** integrációt.
5. Visszaállításhoz tiltsd le az Anthbot Map integrációt, engedélyezd újra a
   régit, majd indítsd újra a Home Assistantot.

A korábbi integráció nyilvántartási bejegyzései miatt az új entitások `_2`,
`_3` vagy más számozott végződést kaphatnak. Ez nem hiba.

## Funkciók

- ANTHBOT-fiók hozzáadása a Home Assistant kezelőfelületéről
- több robot kezelése egy ANTHBOT-fiókból
- felhőalapú állapotfrissítés és AWS IoT/MQTT shadow-kapcsolat
- automatikus MQTT-újracsatlakozás
- natív Home Assistant `lawn_mower` entitás
- teljes terület, kézi zóna és automatikus zóna nyírása
- külső szegély és töltőállomás körüli nyírás
- nyírás szüneteltetése, folytatása és leállítása
- visszaküldés a töltőállomásra
- akkumulátor-, töltés-, állapot-, RTK-, hálózat-, firmware- és karbantartási
  adatok
- térkép-, zóna-, hiba- és diagnosztikai entitások
- aktuális nyírási útvonal és lenyírt terület
- korábbi nyírási feladatok terület-, térkép- és útvonalrészletekkel
- saját kertfotó használata háttérként
- teljes képernyős térkép, nagyítás, mozgatás és forgatás
- külön térkép-, robot-, útvonal- és határvonal-kalibráció
- a kártyáról kimásolható YAML-konfiguráció
- 23 választható nyelv

## Követelmények

- Home Assistant 2024.1.0 vagy újabb
- HACS az ajánlott telepítéshez
- működő ANTHBOT-fiók
- internetkapcsolat az ANTHBOT felhő eléréséhez

# Telepítés

## Telepítés HACS használatával

### 1. Az egyéni repository hozzáadása

1. Nyisd meg a **HACS -> Integrációk** oldalt.
2. A jobb felső hárompontos menüben válaszd az **Egyéni tárolók / Custom
   repositories** lehetőséget.
3. Add hozzá ezt a címet:

   ```text
   https://github.com/Mqbretrofit/ha-anthbot-map-v2
   ```

4. Kategóriának válaszd az **Integration** lehetőséget.
5. Kattints a **Hozzáadás / Add** gombra.

### 2. Az integráció telepítése

1. A HACS-ban keresd meg az **Anthbot Map** integrációt.
2. Telepítsd a legújabb stabil verziót.
3. Indítsd újra a Home Assistantot.

A térképkártyát nem kell külön HACS dashboard repositoryból telepíteni. Az
`anthbot-map-card` az integráció része, és az integrációval együtt frissül.

### 3. Az ANTHBOT-fiók hozzáadása

1. Nyisd meg a **Beállítások -> Eszközök és szolgáltatások** oldalt.
2. Kattints az **Integráció hozzáadása** gombra.
3. Keresd meg az **Anthbot Map** integrációt.
4. Add meg az ANTHBOT-fiókod adatait.
5. Várd meg, amíg a Home Assistant létrehozza a robothoz tartozó eszközt és
   entitásokat.

## Lovelace-erőforrás

Storage módú Lovelace használatakor az integráció automatikusan létrehozza vagy
frissíti ezt a JavaScript-erőforrást:

```text
/anthbot-map-v2/anthbot-map-card.js
```

Az erőforrás típusa: **JavaScript module**. Normál telepítésnél ezt nem kell
kézzel hozzáadni.

### Ha az erőforrás nem jött létre automatikusan

1. Nyisd meg a **Beállítások -> Irányítópultok -> Erőforrások** oldalt.
2. Adj hozzá egy új erőforrást:

   ```text
   /anthbot-map-v2/anthbot-map-card.js?v=2.4.2
   ```

3. Típusnak válaszd a **JavaScript module** lehetőséget.
4. Indítsd újra a Home Assistantot, majd nyomj `Ctrl+Shift+R`-t.

Egyszerre csak egy Anthbot Map Card-erőforrás legyen engedélyezve.

## Kézi telepítés

1. Töltsd le a legújabb kiadás ZIP-fájlját.
2. Másold a `custom_components/anthbot_map/` mappát a
   `/config/custom_components/anthbot_map/` mappába.
3. Indítsd újra a Home Assistantot.
4. Nyisd meg a **Beállítások -> Eszközök és szolgáltatások** oldalt, és add
   hozzá az **Anthbot Map** integrációt.

# A térképkártya hozzáadása

## Minimális konfiguráció

A **Fejlesztői eszközök -> Állapotok** oldalon keresd meg az integráció által
létrehozott térképentitást. Az entitásazonosító általában `_map` végződésű.

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
```

A `sensor.YOUR_MOWER_map` helyére a saját térképentitásodat kell írni.

## Saját kertfotó használata

Másold a kert felülnézeti képét például a `/config/www/garden.jpg` helyre, majd
így hivatkozz rá:

```yaml
image: /local/garden.jpg
```

A legjobb eredményhez felülnézeti, lehetőleg torzításmentes légi vagy
drónfelvétel használata ajánlott.

## Ajánlott teljes konfiguráció

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
image: /local/garden.jpg
height: 720
fit: cover
refresh_interval: 3
robot_heading_source: cloud
robot_heading_offset: 0
mowed_path_color: rgba(255, 235, 59, 0.82)
mowed_path_width: 10
boundary_width: 3
boundary_color: rgba(74, 101, 255, 0.9)
show_zones: true
show_no_go_zones: true
show_no_go_labels: true
show_mowed_path: true
show_decoded_boundary: true
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

# Kalibráció

A négy kalibrációs rész eltérő térképréteget szabályoz.

## Térkép illesztése

A `calibration` blokk az ANTHBOT teljes térképi koordinátarendszerének
alapillesztését végzi el a kertfotóhoz. Ezt állítsd be először.

```yaml
calibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Robot kalibráció

A `robotCalibration` a robotikon helyzetének, méretének és
iránykorrekciójának finomhangolására használható. Nem forgatja el a nyírási
útvonalat.

```yaml
robotCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## Nyírási útvonal kalibráció

A `mowingPathCalibration` külön mozgatja, méretezi és forgatja az aktuális és
korábbi nyírási útvonalakat, valamint a lenyírt terület megjelenítését.

```yaml
mowingPathCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

Ez a kalibráció független a robotikon irányától.

## Határvonal kalibráció

A `decodedBoundaryCalibration` a dekódolt gyephatárvonal külön illesztésére
használható.

```yaml
decodedBoundaryCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

## A kalibráció ajánlott sorrendje

1. A **Térkép illesztése** résznél igazítsd a teljes térképet a kertfotóhoz.
2. A **Nyírási útvonal kalibrációja** résznél illeszd az útvonalat és a
   lefedettséget.
3. A **Robot kalibrációja** résznél állítsd be a robotikont és annak irányát.
4. A **Határvonal illesztése** résznél igazítsd a dekódolt határvonalat.
5. Kattints a **YAML másolása** gombra, és mentsd el az elkészített beállítást.

Az `offsetX`, `offsetY`, `scaleX` és `scaleY` arányértékek. A kalibrációs
blokkokban a `rotation` értéke radiánban értendő.

# A robot haladási iránya

Ajánlott beállítás:

```yaml
robot_heading_source: cloud
```

Elérhető módok:

- `cloud`: a hivatalos alkalmazással kompatibilis felhőalapú `pose.yaw`;
  ajánlott;
- `movement`: az irány kiszámítása az egymást követő pozíciókból;
- `auto`: elsődlegesen a mozgási irányt használja, szükség esetén pedig a
  felhőadatokra vált.

A hivatalos alkalmazás a `pose.yaw` értékét milliradiánként kezeli. A kártya
ugyanezt az átváltást használja:

```text
fok = yaw * 180 / (pi * 1000)
```

Fix képi szögeltérésnél használható:

```yaml
robot_heading_offset: 0
robot_image_rotation: 90
```

Ez a két érték fokban értendő.

# Nyírási előzmények

1. Nyisd meg az **Anthbot Map** kártyát.
2. Nyisd ki a jobb alsó sarokban található lebegő menüt.
3. Válaszd a **Diagnosztika** fület.
4. Nyisd le a **Korábbi nyírási feladatok** részt.
5. Kattints egy befejezett nyírásra.

Az előzmények megjeleníthetik a dátumot, időtartamot, lenyírt területet,
folyamatot, nyírási módot, indítási okot, zónákat, valamint a korábbi terület-,
térkép- és útvonaladatokat.

A lista körülbelül ötpercenként frissül az ANTHBOT felhőből. A részletes képi
nézet csak akkor nyílik meg, ha a felhőrekord tartalmaz terület-, térkép- vagy
útvonalfájlt. Az összefoglaló képi fájl nélkül is látható marad.

# Nyelv beállítása

Alapértelmezésben a kártya a Home Assistant kezelőfelületének nyelvét követi:

```yaml
language: auto
```

Támogatott nyelvek: angol, magyar, német, francia, spanyol, olasz, portugál,
holland, lengyel, cseh, szlovák, román, dán, svéd, norvég, finn, egyszerűsített
kínai, hagyományos kínai, török, thai, vietnámi, koreai és khmer. Nem támogatott
nyelvnél a kártya angolra vált.

# Frissítés

HACS használata esetén:

1. Telepítsd a HACS által felajánlott frissítést.
2. Indítsd újra a Home Assistantot.
3. Frissítsd a böngészőt `Ctrl+Shift+R` használatával.

Storage módú Lovelace esetén az integráció automatikusan frissíti az erőforrás
verzióparaméterét. YAML erőforrásmódban frissítés után módosítsd a
gyorsítótárat megkerülő verzióparamétert, például:
`/anthbot-map-v2/anthbot-map-card.js?v=2.4.2`.

# Hibaelhárítás

## A kártya nem található

Ellenőrizd, hogy:

- telepítve van-e az Anthbot Map, és újraindult-e a Home Assistant;
- létezik-e a `/config/www/anthbot-map-v2/anthbot-map-card.js` fájl;
- szerepel-e az erőforrások között az `/anthbot-map-v2/anthbot-map-card.js`;
- az erőforrás típusa **JavaScript module**-e;
- nincs-e engedélyezve egy régi, duplikált Anthbot Map Card-erőforrás.

Ezután nyomj `Ctrl+Shift+R`-t.

## Nem jelenik meg a térkép

Ellenőrizd, hogy a helyes térképentitás van-e megadva, az állapota `ready`-e,
és az attribútumai között megtalálható-e a `pose` és a térképadat. Ellenőrizd a
Home Assistant naplójában az `anthbot_map` hibákat is.

M5/M9 modellen a térképes megjelenítés ismert korlátozás miatt jelenleg nem
működik.

## A robot iránya hibás

Elsőként használd a `robot_heading_source: cloud` beállítást. Ha a robotikon
állandó szögeltéréssel jelenik meg, állítsd be a `robot_heading_offset` értékét,
majd finomhangold a **Robot kalibrációja** résznél.

## Nem jelennek meg a nyírási előzmények

Ellenőrizd, hogy 2.3.0 vagy újabb verzió van-e telepítve, a megfelelő robot
térképentitását használod-e, szerepel-e `mowing_records` az attribútumok között,
működik-e a felhőkapcsolat, és eltelt-e legalább öt perc az utolsó frissítés
óta.

# Hibabejelentés

Hibát itt lehet bejelenteni:

https://github.com/Mqbretrofit/ha-anthbot-map-v2/issues

Hibabejelentés előtt töröld vagy takard ki a jelszavakat, bearer tokeneket,
AWS-azonosítókat és kulcsokat, robotsorozatszámokat, PIN-kódokat,
GPS-koordinátákat, kertfotókat és más személyes adatokat.

# Köszönet

- https://github.com/vincentjanv/anthbot_genie_ha
- https://github.com/AdrianTIonut/anthbot_genie_ha
- https://github.com/reloxx13/ioBroker.anthbot-genie

# Licenc

MIT - részletek a [LICENSE](LICENSE) fájlban.
