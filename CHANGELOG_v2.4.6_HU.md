# Anthbot Map v2.4.6 – Magyar összefoglaló

## Statisztikák és diagnosztikák

- Bekerült az opcionális, névtelen használati statisztika az integráció telepítéseinek, modelljeinek és verzióinak jobb áttekintéséhez.
- Bekerült az opcionális automatikus diagnosztikai riport az újonnan aktív robot-hibakódokhoz és felhős task-event hibákhoz.
- Az automatikus hibariport tartalmazza a szükséges robotállapotot, firmware-környezetet, esemény-/hibakódokat és a hibakereséshez szükséges, szűrt diagnosztikai adatokat.
- A két funkció külön kapcsolható az **Anthbot Map → Beállítások → Fejlesztés és diagnosztika** menüben.
- Mindkét küldési lehetőség **alapértelmezetten kikapcsolt**, és csak akkor küld adatot, ha a felhasználó kifejezetten engedélyezi.
- A riportok a projekt saját `reports.mqbretrofithungary.online` szerverére érkeznek, az ANTHBOT/TMT gyártói infrastruktúrától elkülönítve.

## N8 támogatás – tesztelésre elérhető

- Az N8-specifikus vezérlés, állapotkezelés, térkép-/útvonalkezelés és modellspecifikus entitások bekerültek, és **tesztelésre elérhetők**.
- Az N8 implementáció **code/API szinten ellenőrizve** van, külön regressziós és modellszeparációs tesztekkel.
- **Valós N8 hardveres teszt még nem készült.** N8 tulajdonosok visszajelzését várjuk, hogy a modellspecifikus működést valódi eszközön is ellenőrizhessük.
- A Genie és M-szériás modellkezelés elkülönítése megmaradt; az N8 támogatás nem bővíti bele az N8-at a meglévő M5/M9 felismerési ágakba.

## Stabilitás és kompatibilitás

- Tartalmazza a v2.4.6 béta sorozat kipróbált módosításait, köztük a v2.4.6-beta.13 automatikus robot-hibariportját.
- Megmaradnak a 2.4.5 működő Genie és M-szériás vezérlései, térkép-/útvonal-/zónakezelése, nyírási előzményei, Battery Saver funkciói és teljesítményjavításai.
- A riportküldés megfigyelő jellegű, a robot vezérlését nem módosítja.
- A meglévő támogatott modellágak ANTHBOT Genie 1000 és M9 Pro valódi hardveren is tesztelve lettek.

## Ellenőrzés

- Automatizált unit/regressziós tesztek.
- HACS validáció.
- Home Assistant hassfest validáció.
- JavaScript szintaxis- és csomagkonzisztencia-ellenőrzés.
