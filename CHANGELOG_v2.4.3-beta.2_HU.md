# Anthbot Map v2.4.3-beta.2 – magyar változáslista

## Több nyírásból tanuló zónaprogress

Ez a béta a v2.4.3-beta.1 teljes kódjára épül, és annak minden meglévő funkcióját megtartja.

- A geometriai `Active zone area` változatlan marad.
- A progress zónánként, illetve zónakombinációnként tanult tényleges nyírási területet használhat.
- A referencia az utolsó 3, felhőoldali `1014` eseménnyel igazoltan befejezett nyírás mediánja.
- Egyetlen minta már ideiglenes referenciát ad; 3 minta után a referencia stabil.
- Köztes töltés, eső miatti visszatérés, alacsony akkumulátoros visszatérés, kézi dokkolás és megszakított feladat nem kerül be a tanulásba.
- A tanult minták Home Assistant újraindítás és integráció-újratöltés után is megmaradnak.
- Amíg nincs tanult minta, a v2.4.3-beta.1 poligonos/No-Go-val korrigált területszámítása marad az alap.
- Az élő és az előzményben megjelenő progress is az adott zónakiválasztáshoz tartozó tanult referenciát használja.
- A progress szenzor attribútumaiban látható a tanult referencia, a minták, a mintaszám és a tanulás állapota.
