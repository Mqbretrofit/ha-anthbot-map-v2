# Anthbot Map térkép Home Assistanthoz

[English](README.md) | [Magyar](README_HU.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Licenc: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Nem hivatalos Home Assistant-integráció és fényképalapú térképkártya az
Anthbot Genie robotfűnyírókhoz. A robotot, a zónákat, a tiltott területeket,
a töltőt és a megtett útvonalat a kert saját felülnézeti fényképén jeleníti meg.

Ez egy önálló integráció, amely a feltüntetett MIT-licencű projektekből
származik; nem azok kiegészítője. A 2-es verzió saját `anthbot_map` domaint
használ, ezért teszteléshez és gyors visszaállításhoz egy másik
Anthbot-integráció mellett is telepítve maradhat.

> [!CAUTION]
> **Ne engedélyezd ezt az integrációt egyszerre a
> `vincentjanv/anthbot_genie_ha`, az AdrianTIonut fork vagy más Anthbot Home
> Assistant-integráció mellett!** Mindkét integráció telepítve maradhat, de az
> Anthbot Map bekapcsolása előtt tiltsd le a régi integráció konfigurációs
> bejegyzését a **Beállítások → Eszközök és szolgáltatások** oldalon. Egyidejű
> futtatásuk egymással versengő felhőkapcsolatokat és ütköző robotparancsokat
> okozhat. Teszteléskor az új entitásazonosítók `_2`, `_3` vagy későbbi végződést kaphatnak, mert a
> letiltott integráció nyilvántartási bejegyzései megmaradnak; így viszont
> újratelepítés nélkül vissza lehet kapcsolni a régi integrációt.

### Tesztelés meglévő Anthbot-integráció mellett

1. Hagyd telepítve a régi integrációt, de tiltsd le a konfigurációs bejegyzését
   a **Beállítások → Eszközök és szolgáltatások** oldalon.
2. Indítsd újra a Home Assistantot, majd add hozzá és teszteld az
   **Anthbot Map** integrációt.
3. Visszaállításhoz tiltsd le az Anthbot Map integrációt, engedélyezd újra a
   korábbit, majd indítsd újra a Home Assistantot. A kettőt ne engedélyezd
   egyszerre.

> [!IMPORTANT]
> **A stabil 2.2.0 legfontosabb újdonsága:** az integráció tartós AWS IoT
> MQTT-over-WebSocket kapcsolatot használ, ezért a robot élő adatai lényegesen
> gyorsabban frissülnek. A parancsok az alkalmazással egyező élő service-shadow
> csatornán jutnak el a robothoz, és az integráció megvárja a robot
> visszaigazolását. A sűrű shadow-üzenetek összevonva jutnak el a Home
> Assistantig, a kapcsolat pedig automatikusan újracsatlakozik.

> Ez a projekt nem áll kapcsolatban az Anthbottal. A forrásokról és a
> védjegyekről a [NOTICE.md](NOTICE.md) fájlban olvashatsz.

## Funkciók

- Anthbot-felhő bejelentkezés a Home Assistant felületén
- több fűnyíró támogatása egy Anthbot-fiókkal
- tartós, alkalmazáskompatibilis AWS IoT/MQTT élő shadow-frissítés és újracsatlakozás
- natív Home Assistant `lawn_mower` entitás indítás, leállítás/szüneteltetés
  és dokkolás vezérléssel
- akkumulátor-, állapot-, töltés-, RTK-, hálózat-, firmware-, karbantartási-,
  térkép-, zóna-, hiba- és diagnosztikai entitások
- teljes terület, kézi zóna és automatikus zóna nyírása
- szüneteltetés, leállítás és visszaküldés a töltőre
- saját légi vagy drónfelvétel használata háttérképként
- zónák, tiltott területek és nyírási útvonal megjelenítése
- az alkalmazás történeti nyírási útvonalának letöltése a felhőből
- a nyírási munkamenet megőrzése nézetváltás és oldalfrissítés után
- opcionális, állítható szélességű lenyírt terület megjelenítése
- teljes képernyő, nagyítás, mozgatás, forgatás és kalibrálás
- lebegő, áttetsző vezérlőmenü, amely mellett a kert térképe látható marad
- látható pozíció- és iránykijelzés
- a hivatalos alkalmazással megegyező milliradiános irányszámítás
- a kalibrálópanelen elkészített YAML közvetlenül kimásolható
- a Home Assistant nyelvének automatikus felismerése és kézi nyelvválasztás
- 23 választható nyelv, köztük az egyszerűsített és hagyományos kínai,
  a török, thai, vietnámi, koreai és khmer

Elsősorban Genie sorozatú fűnyírókkal tesztelve. Az elérhető adatok és
parancsok modellenként és firmware-verziónként eltérhetnek.

## A repository felépítése

```text
custom_components/anthbot_map/   Home Assistant-integráció
www/anthbot-map/                        Lovelace térképkártya
tools/anthbot_dump.py                   Opcionális diagnosztikai segédprogram
examples/                               Minta YAML
```

## Telepítés HACS használatával

1. Nyisd meg a **HACS → Integrációk** oldalt.
2. A jobb felső hárompontos menüben válaszd az **Egyéni tárolók / Custom
   repositories** lehetőséget.
3. Add hozzá ezt a címet:

   ```text
   https://github.com/Mqbretrofit/ha-anthbot-map-v2
   ```

4. Kategóriának válaszd az **Integration** lehetőséget.
5. Telepítsd az **Anthbot Map** integrációt.
6. Indítsd újra a Home Assistantot.
7. Nyisd meg a **Beállítások → Eszközök és szolgáltatások → Integráció
   hozzáadása** oldalt.
8. Keresd meg az **Anthbot Map** integrációt, majd add meg az
   Anthbot-fiókod adatait.

A HACS az integrációt telepíti és a későbbi frissítéseket kezeli. A GitHub
Release oldalról letölthető teljes ZIP az integrációt, a kártyát, a mintát és
a dokumentációt egyben tartalmazza.

## A térképkártya telepítése

A kártya az integráció része, ezért a HACS automatikusan telepíti és frissíti.
Az integráció az első betöltésekor automatikusan a
`/config/www/anthbot-map-v2/` mappába is tükrözi a frontendfájlokat. Így a
kártya akkor is betöltődik, ha teszteléshez az Anthbot Map v2 bejegyzését
letiltod, és a régi Anthbot-integrációt engedélyezed.

Storage módú Lovelace használatakor az integráció ezt a JavaScript-erőforrást
automatikusan létrehozza vagy frissíti:

```text
/anthbot-map-v2/anthbot-map-card.js
```

Az erőforrás típusa: **JavaScript module**. YAML erőforrásmódban ezt kézzel
kell hozzáadni. Az erőforráskezelő általában a
**Beállítások → Irányítópultok → jobb felső hárompontos menü → Erőforrások**
oldalon található. Ezután indítsd újra a Home Assistantot, majd nyomj
`Ctrl+Shift+R`-t a böngészőben.

Egyszerre csak az egyik Anthbot Map kártyaerőforrás legyen engedélyezve. A HACS
a stabil URL mögötti fájlt automatikusan frissíti, ezért a későbbi kiadásoknál
nem kell átírni az erőforrás címét.

## Kézi integrációtelepítés

Másold a `custom_components/anthbot_map/` mappát ide:

```text
/config/custom_components/anthbot_map/
```

Ezután indítsd újra a Home Assistantot, és add hozzá az integrációt az
**Eszközök és szolgáltatások** oldalon.

## Minimális kártyabeállítás

A **Fejlesztői eszközök → Állapotok** oldalon keresd meg a térkép entitását.
Az entitásazonosító általában `_map` végződésű.

```yaml
type: custom:anthbot-map-card
entity: sensor.YOUR_MOWER_map
name: Anthbot Map
image: /local/garden.jpg
height: 720
fit: cover
robot_heading_source: cloud
refresh_interval: 2
show_zones: true
show_no_go_zones: true
show_no_go_labels: true
show_mowed_path: true
show_decoded_boundary: true
```

A `sensor.YOUR_MOWER_map` helyére írd a saját entitásazonosítódat. A háttérkép
nem kötelező. Ha használod, másold például a `/config/www/garden.jpg` helyre,
majd a kártyán `/local/garden.jpg` néven hivatkozz rá.

## A térkép kalibrálása

1. Nyisd meg a kártyát, majd válts teljes térképes nézetre.
2. Nyisd meg a **Beállítások** panelt.
3. Igazítsd a térképet, a robotot és a dekódolt határvonalat a fényképhez.
4. Másold ki az elkészített YAML-konfigurációt.
5. Cseréld le vele a kártya jelenlegi beállítását.

A kalibráció minden kertnél egyedi. Példa:

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
  rotation: 0
decodedBoundaryCalibration:
  offsetX: 0
  offsetY: 0
  scaleX: 1
  scaleY: 1
  rotation: 0
```

A kalibrációs blokkokban a forgatás értéke radiánban értendő.

## A robot iránya

Ajánlott beállítás:

```yaml
robot_heading_source: cloud
```

A hivatalos Anthbot alkalmazás a `pose.yaw` értéket milliradiánként kezeli.
A kártya ugyanazt az átváltást használja:

```text
fok = yaw * 180 / (pi * 1000)
```

Választható irányforrások:

- `cloud` – a hivatalos alkalmazással megegyező `pose.yaw`; ajánlott
- `movement` – az irány kiszámítása az egymást követő pozíciókból
- `auto` – elsődlegesen a mozgás iránya, tartalékként a felhőből érkező irány

Ha a robot képe fix szögeltéréssel jelenik meg:

```yaml
robot_heading_offset: 0
robot_image_rotation: 90
```

Mindkét érték fokban értendő.

## Nyelv kiválasztása

Alapértelmezésben a kártya a Home Assistant kezelőfelületének nyelvét követi.
A kártya **Beállítások** paneljén ettől eltérő nyelv is választható. A választás
a böngészőben megmarad, és a kimásolt YAML-ba is bekerül.

```yaml
language: auto
```

Elérhető nyelvek: angol, magyar, német, francia, spanyol, olasz, portugál,
holland, lengyel, cseh, szlovák, román, dán, svéd, norvég, finn, egyszerűsített
kínai és hagyományos kínai. Nem támogatott nyelvnél a kártya angolra vált.

## Frissítés

### Csak térkép mód

Floorplan fölötti megjelenítéshez a kártya minden kezelőeleme elrejthető:

```yaml
map_only: true
transparent_background: true
```

A `transparent_background` eltávolítja a háttérképet és a vászon kitöltését,
de a háttérkép oldalarányát és kalibrációját továbbra is felhasználja a pontos
floorplan-illesztéshez.

Mindkét opció kapcsolható a **Felület beállítások** fülön. A választás az adott
böngészőben megmarad. Csak térkép módban dupla kattintással vagy dupla
koppintással visszahozható a teljes kezelőfelület.

Az üveghatás külön kapcsolható, és nem teszi teljesen átlátszóvá a kártyát:

```yaml
glass_background: true
```

A `glass_background` és a `transparent_background` egyszerre nem aktív.

A Home Assistant theme színeinek átvétele külön engedélyezhető:

```yaml
theme_background: true
```

Alapértéke `false`, ezért bekapcsolás nélkül a kártya a saját sötét színeit használja.

### Egyedi gombműveletek

A `start`, `stop`, `dock`, `outer-edge`, `dock-edge` és `connect` gombokhoz
tetszőleges Home Assistant service vagy script rendelhető. Például zárt
fűnyíróház felnyitását és ellenőrzését végző script indításához:

```yaml
button_actions:
  start:
    service: script.anthbot_biztonsagos_inditas
  dock:
    service: script.anthbot_biztonsagos_toltes
```

A nem felülírt gombok továbbra is a gyári Anthbot műveletet használják.

A kártyafájlok frissítése után módosítsd a Lovelace-erőforrás címének végén a
verziószámot, hogy a böngésző ne a régi fájlt használja, majd indítsd újra a
Home Assistantot és nyomj `Ctrl+Shift+R`-t.

## Hibaelhárítás

### A kártya nem található

- ellenőrizd, hogy az erőforrás típusa JavaScript module
- ellenőrizd a `/config/www/anthbot-map/anthbot-map-card.js` fájlt
- nyisd meg közvetlenül az `/anthbot-map-v2/anthbot-map-card.js` címet
- frissítsd az oldalt `Ctrl+Shift+R` használatával

### Nem látható a térkép vagy a robot

- ellenőrizd, hogy a térképentitás állapota `ready`
- nézd meg, hogy az attribútumok között van-e `pose` és `area_definition`
- várd meg a következő felhőfrissítést
- ellenőrizd a Home Assistant naplójában az `anthbot_map` bejegyzéseket

### Az irány csak körülbelül −40° és +40° között változik

A böngésző valószínűleg régebbi kártyaverziót használ. A 79-es verzió már
helyesen váltja át a milliradiánt. Frissítsd az erőforrás címét, majd nyomj
`Ctrl+Shift+R`-t.

## Hibabejelentés

Hibát itt jelenthetsz:
[github.com/Mqbretrofit/ha-anthbot-map-v2/issues](https://github.com/Mqbretrofit/ha-anthbot-map-v2/issues).

Soha ne tegyél közzé jelszót, tokent, robot-sorozatszámot, PIN-kódot,
GPS-koordinátát, kertfotót vagy kitakarás nélküli diagnosztikai fájlt.

## Köszönet és felhasznált projektek

- [vincentjanv/anthbot_genie_ha](https://github.com/vincentjanv/anthbot_genie_ha)
- [AdrianTIonut/anthbot_genie_ha](https://github.com/AdrianTIonut/anthbot_genie_ha)
- [reloxx13/ioBroker.anthbot-genie](https://github.com/reloxx13/ioBroker.anthbot-genie)

## Licenc

MIT – lásd a [LICENSE](LICENSE) fájlt.
