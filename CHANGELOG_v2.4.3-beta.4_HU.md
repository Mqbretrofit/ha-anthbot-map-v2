# Anthbot Map v2.4.3-beta.4 – változások

Ez a béta a **v2.4.3-beta.3** teljes funkcionalitására épül, és a Genie, M5, M9 és M9 Pro modellek kezelését modellfüggő rétegekre választja szét.

## Fő változások

- Elkülönült a **Genie** és az **M-széria (M5/M9/M9 Pro)** modellfüggő működése, hogy az egyik modell javítása ne írja felül a másik vezérlését.
- Helyreállt és pontosabb lett az **M9/M9 Pro térképhatár, nyírási útvonal és zónakezelés**, beleértve a map-manager `area_setting.json` zónáit.
- Az M-széria indítás/szünet/folytatás/leállítás parancskezelése az alkalmazásban megfigyelt protokollhoz igazodik; az M9 Pro leállítás a `stop_all_tasks` parancsot a szükséges skalár `data = 1` értékkel küldi.
- A zónanyírás az M-szérián a kiválasztott zónaazonosítókat használja, a futó feladatnál pedig az `active_area.id` alapján követhető az aktív zóna.
- Javult az **M-széria nyírási előzményeinek** zónafelismerése és a futó/befejezett feladatok elkülönítése. A régebbi, hiányos előzményeknél a helyadat-alapú zónakeresés csak óvatos tartalék módszerként használható.
- A kártya vezérlői, beállításai és kapcsolódó entitásai **robot-sorozatszámhoz kötve** választódnak ki, ami javítja a több robot egyidejű használatát.
- Javult a **Genie élő állapotfrissítése** úgy, hogy az M-széria modellfüggő működése ettől független marad.
- A felület elrejti az adott modellen nem támogatott funkciókat.
- Modellfüggő robotképek kerültek be: **M9 Pro saját képet**, **M9 és M5 M9 képet** kap; a **Genie eredeti robotképe változatlan marad**.

## Megjegyzés

Ez továbbra is béta kiadás. Az M-széria nyírási előzményeiben az alkalmazás által mutatott százalék közvetlen felhőforrásának feltárása külön folyamatban van; ez a kiadás nem állítja, hogy minden régi előzmény százalékértéke már az alkalmazással teljesen azonos.
