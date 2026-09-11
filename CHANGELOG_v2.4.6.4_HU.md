# Anthbot Map v2.4.6.4

## Javítások

- Az automatikus diagnosztika most esemény-élre működik: ugyanaz a tartós `no_go_path_crossing` vagy más változatlan diagnosztikai állapot nem küldődik újra óránként.
- Home Assistant/integráció újraindításakor a már fennálló régi diagnosztikai állapot kiindulási állapotként kerül felvételre, ezért nem generál újabb riportot csak az újraindítás miatt.
- A régi cloud task-event hibák megmaradnak előzményként, de friss/elavult jelölést kapnak, és az elévült esemény önmagában már nem indít automatikus hibariportot.
- Az AWS IoT live-shadow figyelő váratlan normál futásidejű/transport hibák után sem áll le végleg, hanem tovább próbál kapcsolódni.
- Többszöri sikertelen reconnect után a kliens új ideiglenes IoT hitelesítőt kér, miközben a normál lejárati frissítés is megmarad.
- Az M5/M9 térképrétegnél külön kezeljük a logikai `map.map_id`, `area_id`, `plan_id` és a `map_manager_<serial>.tar.gz` belsejében lévő raster `map_id` értékeket.
- A különböző logikai és raster map ID többé nem okoz felesleges map-manager újraletöltést.
- A legacy M-series fallback többé nem képez `map_manager_<map_id>.tar.gz` fájlnevet a logikai map ID-ból.

A Genie, M5/M9 és N8 modellek útvonalai továbbra is elkülönítve maradnak; az M-series térképjavítás nem bővíti az N8 vezérlési útvonalát.
