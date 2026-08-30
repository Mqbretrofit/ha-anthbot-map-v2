# Anthbot Map v2.4.1 – magyar változáslista

## Stabil akkumulátorkímélő kiadás

- Három kész akkukímélő profil került be: **Max. akkukímélés**,
  **Kiegyensúlyozott** és **Mindig indulásra kész**, valamint megmaradt a teljesen
  állítható **Egyéni** profil.
- Robotenként tartósan menti a felső töltési határt, a fenntartó töltés indítási
  szintjét, a félbehagyott feladat folytatási szintjét, a közös RTK-táp
  beállítását, az aktuális működési fázist és a shutdown-védelem időzítését.
  A Home Assistant újraindítása már nem indítja újra az aktív ciklust.
- Bekerült az 55+1 perces anti-shutdown védelem: dokkolt, készenléti robotnál,
  kikapcsolt töltőtáp esetén 55 perc után egy percre bekapcsolja a töltőt, majd
  újrakezdi a ciklust.
- A kártyán látható a shutdown-védelem állapota és a következő impulzusig
  hátralévő idő, beleértve az inicializálást és az aktív ébresztő töltést.
- A normál fenntartó töltés különválik a rövid ébresztő impulzustól, és hiányzó
  robot-telemetria esetén a rendszer nem kapcsolja le vakon a tápot.
- Helyesen kezeli a közös és a külön RTK-tápot nyírás, dokkhoz visszatérés,
  töltés és RTK-inicializálás közben.
- Az akkumulátorkímélő mód kikapcsolásakor azonnal visszakapcsolja a töltőtápot,
  a kézzel elindított töltést pedig nem téveszti össze automatikus
  akkukímélő-váltással.
- Javult az integráció leállítása és újratöltése; a mentett beállítások Home
  Assistant-újraindítás nélkül, azonnal életbe lépnek.
- Az akkukímélő csempe csak a beállítóablakot nyitja meg; a nagyobb be- és
  kikapcsoló jelölőnégyzet a popupban marad.
- Az új akkukímélő felület mind a 23 támogatott nyelven elérhető.

Ez a stabil kiadás váltja a teljes `v2.4.1-beta` sorozatot.
