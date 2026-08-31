# Anthbot Map v2.4.3-beta.1 – magyar változáslista

## Nyírási folyamat, mozgatható élő státusz és induló menüelrendezés

Ez a béta a v2.4.2 kódjára épül, és a meglévő akkukímélő, egyéni gomb, RTK, vezérlési, fordítási és újraindítás utáni állapotmentési funkciókat megtartja.

- Új, végleges nevű `Mowing progress` és `Active zone area` szenzorok; az integráció nem hoz létre `_test` nevű progress entitást.
- Az aktív célterületből csak a ténylegesen átfedő No-Go terület kerül levonásra.
- Egy és több zóna, valamint teljes területes nyírás kezelése.
- Az akkumulátor/állapot mellett látszik az éppen nyírt cél és a számolt százalék; a státuszblokk húzható és megjegyzi a helyét.
- Normál befejezésnél 95%-tól 100%-nak jelenik meg a feladat, és ez töltés/készenlét alatt is megmarad a következő nyírásig.
- Az előzmények százaléka a lenyírt terület és a nettó célterület alapján újraszámolódik.
- Benne van a PR #24: `default_panel`, `menu_open`, `default_submenu`.
- A frontend átmenetileg felismeri a régi `_test` progress szenzort fallbackként, de új `_test` entitás nem készül.
- A `mowing_progress` kikerült a legacy entity cleanup listából, ezért az új végleges szenzort a HA újraindítás/reload nem törli ki.

Ez egy béta kiadás valós eszközös teszteléshez.
