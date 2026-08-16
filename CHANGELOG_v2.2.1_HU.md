# Anthbot Map v2.2.1 – változások

- A külső szegélynyírás most a gyári alkalmazás által használt `ridable_mow_start` paranccsal indul.
- Javítva, hogy a kiválasztott szegélynyírás után ne indulhasson el tévesen a teljes terület nyírása.
- A robot pozíciója folyamatosan frissül MQTT-ről; javult az MQTT-hitelesítés helyreállítása is.
- Javítva az élő robotpozíció prioritása és az irány megjelenítése.
- Új regressziós tesztek készültek a szegélynyíráshoz, a folytatáshoz és az MQTT-helyreállításhoz.
