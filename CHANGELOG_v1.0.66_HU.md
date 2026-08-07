# Anthbot Map v1.0.66 – változások

## Akkumulátorszenzor javítása

- Az M5 Lidar modellek `elec: {"value": ...}` akkumulátor-adatformátuma támogatott.
- A korábbi modellek közvetlen `elec: 85` formátuma továbbra is működik.
- Az akkumulátorérték egységesen egész számmá alakul.
- A hiányzó, hibás vagy 0–100 tartományon kívüli érték nem hoz létre érvénytelen Home Assistant szenzorállapotot.
- A feldolgozás külön, tesztelhető `_battery_level()` függvénybe került.

## Hatás

Az akkumulátorszenzor az M5 Lidar és a korábbi Anthbot modellek eltérő felhős adatstruktúrájával is helyesen működik.
