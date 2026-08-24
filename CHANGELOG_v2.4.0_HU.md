# Anthbot Map v2.4.0 – magyar változáslista

## Akkumulátorkímélő nyírási mód

Ez a kiadás opcionális akkumulátorkímélő módot ad a Home Assistant `switch`
entitással vezérelt robottöltőkhöz.

- Külön beállítható a felső töltési határ, a nyugalmi fenntartó töltés
  visszakapcsolási szintje és a megszakított nyírás folytatási töltöttsége.
- Ha az ANTHBOT felhő `1021` eseménye igazolja az alacsony akkumulátor miatti
  visszatérést, az integráció a folytatási szintig tölt, majd folytatja a
  megjegyzett feladatot.
- A Home Assistantból indított teljes, kézi zóna-, automatikus zóna-, szegély-
  és töltőkörüli nyírás feladatspecifikus adatai megmaradnak.
- Kézi visszaküldés vagy befejezett feladat után nem indul újra a nyírás.
- A töltő automatikus bekapcsolásakor a robot ideiglenesen elnémul, majd
  visszaáll az előző hangerő.
- Az állapot mentésre kerül, ezért a Home Assistant újraindítása sem veszíti el
  a folytatható feladatot vagy az ideiglenesen eltett hangerőt.

Az ANTHBOT felhő nem biztosít megbízható élő nyírási százalékot. A funkció ezért
nem becsült értéket használ, hanem a felhő megerősített feladateseményeiből
működik.

## Új entitások

- Felhő feladatesemény-kód
- Felhő feladatesemény szövege
- Felhő feladatesemény típusa
- Felhő feladatesemény időpontja
- Akkumulátorkímélő mód kapcsoló

> A funkció opcionális, és csak a töltőkapcsoló beállítása, valamint az
> Akkumulátorkímélő mód bekapcsolása után aktív.
