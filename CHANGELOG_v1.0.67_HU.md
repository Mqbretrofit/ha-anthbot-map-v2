# Anthbot Map v1.0.67 – változások

## M5/M9 térképtámogatás

- Az M5 és M9 LiDAR modellek térképe az alkalmazással azonos `multi_maps` archívumból töltődik le.
- A dekóder kezeli a nyers TAR, gzip és zlib tömörítésű térképarchívumokat.
- A térképfájl kiválasztása a készülékfelhő `multi_maps.map_list` adatai alapján történik.
- A térkép automatikusan frissül a fájl, az időbélyeg vagy az MD5 változásakor.
- Hiányzó vagy átmenetileg hibás térkép esetén az integráció minden lekérdezési ciklusban újrapróbálkozik.
- A korábbi Genie modellek régi térképformátumának támogatása megmaradt.

## Tesztek

- 13 automatikus teszt ellenőrzi a nyers TAR, gzip és zlib archívumokat, valamint a hibás és hiányos bemenetek kezelését.

## Köszönet

Köszönet @ndoty közreműködéséért, az M5 készüléken végzett ellenőrzésért és a tesztekért.
