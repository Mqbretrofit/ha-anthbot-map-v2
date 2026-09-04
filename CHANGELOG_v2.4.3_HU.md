# Anthbot Map v2.4.3 – változások

Stabil kiadás a v2.4.3 béta sorozat terepen tesztelt állapotára építve. A meglévő Genie működés megmarad, miközben az M5/M9/M9 Pro modellfüggő támogatása külön rétegekben áll össze.

## Fő változások

- Elkülönült a **Genie** és az **M-széria (M5/M9/M9 Pro)** modellfüggő működése, hogy az egyik robot javítása ne írja felül a másik vezérlését.
- Helyreállt és pontosabb lett az **M9/M9 Pro térképhatár, nyírási útvonal és zónakezelés**, beleértve a map-manager `area_setting.json` zónáit.
- Az M-széria indítás/szünet/folytatás/leállítás parancskezelése az alkalmazásban megfigyelt protokollhoz igazodik; az M9 Pro leállítás a `stop_all_tasks` parancsot a szükséges `data = 1` értékkel küldi.
- A zónanyírás az M-szérián a kiválasztott zónaazonosítókat használja, az aktív zóna pedig az `active_area.id` alapján követhető.
- Javult az **M-széria nyírási előzményeinek zónaazonosítása**, így a kártya a helyes zónával tudja használni a saját számított nyírási százalékát.
- A régebbi, hiányos előzményeknél a helyadat-alapú zónakeresés csak tartalék módszer marad.
- A kártya vezérlői, beállításai és kapcsolódó entitásai **robot-sorozatszámhoz kötve** választódnak ki, ami biztonságosabb több robot egyidejű használatánál.
- Javult a **Genie élő állapotfrissítése** az M-szériától függetlenül.
- A felület elrejti az adott modellen nem támogatott funkciókat.
- Visszakerültek a modellfüggő robotképek: **M9 Pro saját képet**, **M9 és M5 M9 képet** kap, a **Genie meglévő képe változatlan marad**.

Ez a kiadás normál, stabil **v2.4.3** kiadás, nem béta és nem tesztverzió.
