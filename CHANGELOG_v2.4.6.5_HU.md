# ANTHBOT Map 2.4.6.5 – változások

Ez a kiadás a 2.4.6.4 stabil működésére épül, és célzott megbízhatósági, diagnosztikai és Recorder-javításokat tartalmaz. A Genie, M5, M9/M9 Pro és N8 vezérlési útvonalai továbbra is külön maradnak.

## Home Assistant event-loop blokkolás

- Megszűnik a `manifest.json` szinkron `read_text()` / `open()` olvasása a Home Assistant event loopból.
- A runtime verziólekérés közös `INTEGRATION_VERSION` konstanst használ.
- A javítás érinti a Developer Opt-in, Developer Agent, developer reporting és firmware-diagnosztika útvonalakat is.
- Regressziós teszt védi, hogy ezekbe a runtime modulokba ne kerülhessen vissza blokkoló manifest-olvasás.

## Automatikus diagnosztikai riportok

- Ugyanaz a `map_definition_error`, `path_definition_error` vagy `live_shadow_error` nem generálhat több száz riportot csak azért, mert a cloud/S3 válaszban változik a `RequestId`, `HostId` vagy a presigned URL.
- A hibák stabil, normalizált signature-t kapnak.
- Coordinatoronként legfeljebb egy automatikus diagnosztikai listener települhet.
- Egy rövid köztes `None` állapot nem nullázza azonnal a hibát: az állapotnak legalább 60 másodpercig ténylegesen tisztának kell lennie, mielőtt ugyanaz a hiba új epizódnak számít.
- Ugyanarra a stabil signature-re egy további 1 órás hard repeat guard is érvényes.
- A no-go signature nem használja a minden új útvonalszegmenssel változó számlálókat.

## M5 / M9 / M9 Pro térkép

- A `map_manager_<serial>.tar.gz` továbbra is a sorozatszám-alapú aktuális M-series térképforrás.
- Az `iot_map.bin` meglévő vektoros dekódere mellé bekerült egy második, LZ4 raster fallback a már bizonyított ANTHBOT map-raster dekóderrel.
- M9/M9 Pro esetén bekerült egy végső, modellhez kötött map-manager mentőút is: ha az aktuális archívum érvényes, de az `iot_map.bin` egyik ismert formátumban sem dekódolható, a használható `area_setting.json` `custom_areas` geometriájából ugyanaz a convex-hull alapú fallback határ készül, amelyet a frontend már korábban is végső megjelenítési tartalékként használt. Így az M9 nem esik tovább a bizonyítottan hiányzó `multi_maps/map_<serial>_0` objektumra.
- Ez a végső zone-hull mentőút csak M9/M9 Pro modellnél aktiválódik; M5 és N8 nem kerül erre az útvonalra.
- Ha a map-manager archívum lejön, de az `iot_map.bin` egyik formátumban sem ismerhető fel, a diagnosztika ezt most külön jelzi, ahelyett hogy csak a későbbi legacy `multi_maps` fallback 404 hibája látszana.
- A diagnosztikában megjelenik a map-manager probe állapota, az archívum neve, az `iot_map.bin` jelenléte/mérete és a dekódolási eredmény. Presigned URL vagy hitelesítési adat nem kerül a riportba.
- A logikai `map_id` / `area_id` / `plan_id` és a raster map id továbbra is külön protokollazonosítóként kezelendő.

## Home Assistant Recorder / adatbázis-növekedés

A terepi mérés során egy friss telepítés `home-assistant_v2.db` fájlja 14,6 GB-ra nőtt. A lekérdezés több, egymástól független ANTHBOT binary sensornál pontosan azonos, több százezres state-sorszámot mutatott. Ennek fő oka az volt, hogy gyorsan változó közös attribútumok (`mowing_time`, `mowing_area`, státuszadatok stb.) minden normál sensorra és binary sensorra rákerültek.

A 2.4.6.5-ben:

- megszűnik a gyorsan változó közös attribútumok fan-outja a normál sensorokon és binary sensorokon;
- a cloud task-event életkor másodpercenként változó attribútuma nem kényszerít felesleges state-változást;
- a mowing-progress részletes debug payloadjai nem kerülnek rá minden normál state-frissítésre;
- a `no_go_path_crossing` Recorder-szempontból csak epizódszintű adatokat tart meg, a minden ponttal változó `checked_point_count` / `checked_segment_count` nem ír új sort;
- a külön pose/GPS sensorok és a device tracker legfeljebb 10 másodpercenként írnak új Home Assistant state-et;
- a Map entity legfeljebb 5 másodpercenként ír Home Assistant state-et, miközben a coordinator továbbra is teljes sebességgel fogadja a cloud live-shadow adatokat;
- a minden live flushnál változó `cloud_last_success` nem kényszerít önmagában új Map state-et.

A javítás a **jövőbeli adatbázis-növekedést** csökkenti. A már meglévő több GB-os Recorder-adatbázist biztonsági okból az integráció nem törli és nem repackeli automatikusan. A régi ANTHBOT history egyszeri törlése/repackje külön, felhasználói jóváhagyással végezhető el.

## Riportok robotonként

- Az új automatikus riportok a teljes sorozatszám helyett csak a biztonságos utolsó 4 karaktert (`serial_suffix`) adják át a Reporting Servernek.
- Így két azonos típusú robot megkülönböztethető például `…0046` és `…0110` formában anélkül, hogy a teljes S/N automatikusan kikerülne.

## Kompatibilitás

- A módosítások nem változtatják meg a mower start/pause/resume/stop parancsokat.
- Genie, M-series és N8 parancs-routing továbbra is elkülönített.
- Az LZ4 raster map fallback M-series guarded marad, a zone-hull végső mentőút pedig csak M9/M9 Pro; az N8 saját modellguardja és vezérlési útvonala változatlan marad.
