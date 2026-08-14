
---

# Anthbot Map v2.1.1 – Magyar változáslista

Ez a stabil kiadás a terepen kipróbált `2.2.1-beta.48` funkciókészletét emeli
stabil verzióvá. Az alábbi változásokat tartalmazza a stabil `2.0.0` verzióhoz
képest.

## A v2.1.1 szegélybeállítási hibajavításai

- Javítva lett a szegélyszerkesztő kezdeti értékeinek betöltése: a kártya most
  az alkalmazással egyező, külön letöltött, aktuális `ridable_area` definíciót
  használja a régebbi, általános területdefinícióba ágyazott másolat helyett.
- Sikeres mentés után az új vágási magasság és szegélyátfedés azonnal bekerül a
  Home Assistant állapotába, ezért a szerkesztő újbóli megnyitásakor már nem
  jelenhet meg akár öt percig a korábbi gyorsítótárazott érték.
- Ugyanez az adatforrás-javítás bekerült az Anthbot Map Cardba és a Garden Map
  Card v163 verziójába is.
- A használható csúcspontok nélküli, üres technikai szegélyrekordok továbbra
  sem jelennek meg.
- A robot továbbra is a teljes szegélylistát kapja meg, ezért a nem módosított
  szegélyek beállításai megmaradnak.

## Alkalmazásszerű nyírási feladatkezelés

- Egyetlen, az ANTHBOT alkalmazáshoz hasonló feladatválasztó került a kártyába.
- Kiválasztható a teljes terület, kézi zóna, automatikus zóna, külső szegély és
  a töltő környéke.
- A kézi és automatikus zónák csak akkor jelennek meg, ha a robot rendelkezik
  ilyen zónákkal.
- Egyszerre egy, kettő vagy az összes rendelkezésre álló zóna kijelölhető.
- Beállítható a kijelölt zónák nyírási sorrendje.
- Zónánként külön kérhető szegélynyírás.
- A kijelölt feladatokat a teljes gomb színezése jelöli.
- Az irányítást egy dinamikus Kezdés, Szüneteltetés és Folytatás gomb végzi.
- A szüneteltetés megtartja az aktuális feladatot.
- A folytatás pontosan az előző teljes területet, kézi vagy automatikus zónákat,
  szegélyt, illetve töltőkörnyéki feladatot indítja újra.
- A folytatható feladat a Home Assistant újraindítása után is megmarad.
- A Leállítás törli a mentett feladatot, így utána nem indítható hibás folytatás.
- Lefordított figyelmeztetés jelenik meg, ha nincs folytatható feladat.
- Visszaállt a beta.35 verzióban bevált, konkrét zónagombokat használó
  parancsútvonal.
- Részletes visszajelzés készült az elküldött, felhő által elfogadott, robot
  által visszaigazolt, elutasított és vissza nem igazolt parancsokhoz.
- A másodlagos nézetekből kikerültek a duplikált zóna-, indítás-, leállítás- és
  töltőgombok.
- Az egérrel és érintéssel használt vezérlők egyetlen kattintásra reagálnak.

## Globális robotbeállítások

- Nyírások száma.
- Szegély mentén történő visszatérés.
- Automatikus töltőkörnyéki nyírás.
- Vizuális akadályérzékelés be- és kikapcsolása.
- Alacsony, közepes és magas vizuális akadályérzékelési érzékenység.
- A vizuális akadályérzékelés és annak érzékenysége egy közös, áttekinthető
  beállításba került.

## Kézi és automatikus zónák beállításai

- Külön beállítási rész készült a kézi és az automatikus zónákhoz.
- Zónánként állítható a nyírások száma és a vágási magasság.
- Zónánként kapcsolható a vizuális akadályérzékelés és beállítható annak szintje.
- Zónánként kapcsolható az egyedi nyírási irány és beállítható a szöge.
- Zónánként kapcsolható a szegélynyírás.
- A módosítás az alkalmazással egyező, teljes `area_set` adatcsomagot küldi, így
  egy zóna beállítása nem írja felül a többi zónát.
- A zónabeállítások lenyithatók, és élő frissítés vagy kijelölés közben is
  megtartják a nyitott vagy csukott állapotukat.
- Javítva lett a kézi és automatikus zónaentitások felismerése és elnevezése.
- Javítva lett három vagy több zóna kijelölése és a nyírási sorrend megőrzése.
- Megszűnt a kattintások továbbterjedése és a gombok szürke villogása.
- Beállítás szerkesztése közben az élő frissítés nem ugrasztja vissza a
  csúszkákat, kapcsolókat vagy a panelt az oldal tetejére.

## Szerkeszthető szegély és szegélyátfedés

- Az integráció letölti és feldolgozza az alkalmazás külön `ridable_area`
  térképfájlját.
- Új, alkalmazáskompatibilis `set_edge_settings` Home Assistant szolgáltatás.
- Szerkeszthető szegélyenként beállítható vágási magasság.
- Választható szegélyátfedés: 5, 7, 10, 13, 15, 17 vagy 20 cm.
- A rendszer a teljes `ridable_area_set` listát küldi, ezért a nem módosított
  szegélyek megmaradnak.
- Alkalmazásszerű vizuális átfedésszerkesztő készült ANTHBOT robotképpel.
- A robot és a mérőnyíl együtt mozog; a távolság mérése a szegélytől a robot
  széléig történik.
- Az üres, törölt vagy csúcspont nélküli szegélyek nem jelennek meg.
- Új `ridable_area_error` diagnosztikai adat.
- A nagy szegélydefiníciók és hibák ki vannak zárva a Recorder előzményeiből.

## Karbantartás, előzmények és diagnosztika

- Külön Karbantartás menü készült.
- Megjelenik a kések, a kamera tisztításának és a töltőérintkezők tisztításának
  hátralévő élettartama.
- Külön nullázási szolgáltatás készült késcsere, kameratisztítás és
  töltőérintkező-tisztítás után.
- Javítva lett a kések, a kamera és a töltőérintkezők értékeinek hozzárendelése,
  így a Karbantartás és Diagnosztika ugyanazokat az adatokat mutatja.
- Megjeleníthetők az alkalmazás API-jából lekért korábbi nyírási feladatok.
- Részletes helyi hibakód-előzmény készült.
- A diagnosztika megjeleníti a felhő, a robot és az élő MQTT kapcsolat állapotát.

## MQTT- és felhőkapcsolat stabilizálása

- Az MQTT-over-WebSocket kapcsolat az ANTHBOT Android 2.15.15 alkalmazás
  működéséhez lett igazítva.
- Az alkalmazással egyező `mqttv3.1` WebSocket-alprotokoll és `okhttp/4.12.0`
  kliensazonosítás használata.
- Az AWS IoT Device SDK JavaScript 2.2.15 CONNECT azonosítása, minden
  kapcsolódáskor új UUID kliensazonosító és 300 másodperces keepalive.
- Javítva lett a SigV4 WebSocket lekérdezés felépítése, és kikerült az
  alkalmazás által nem használt `X-Amz-Expires` paraméter.
- Az aláírt lekérdezés változtatás nélkül jut el az AWS-hez.
- Az alkalmazás által kiadott ideiglenes AWS hitelesítő adatok a valódi
  lejáratukig megmaradnak.
- Megszűnt az átmeneti 403/404 válaszok utáni folyamatos hitelesítőadat-csere,
  amely érvényteleníthette a már aláírt kapcsolatot.
- Javítva lett az időtartamként érkező hitelesítőadat-lejárat feldolgozása.
- Tartós automatikus újracsatlakozás készült korlátozott, fokozatos várakozással.
- Az integráció csak az alkalmazás és a robot IoT-jogosultsága által használt
  named-shadow válaszcsatornákra iratkozik fel.
- Az MQTT csak sikeres CONNACK és SUBACK után jelenik meg online állapotként.
- Egy WebSocket-keretben érkező több MQTT-csomag feldolgozása is támogatott.
- A parancsok az alkalmazáshoz hasonlóan az aktív MQTT service-shadow
  kapcsolaton keresztül jutnak el a robothoz.
- Kikerült a félrevezető HTTP parancspótlás, amelyet a felhő elfogadhatott úgy,
  hogy a robot nem hajtotta végre.
- Biztonságosan szűrt, részletes AWS kézfogási hibadiagnosztika készült.

## Kártya és mobilos felület

- A Garden Map Card bevált mobilos elrendezése került az Anthbot Map Cardba.
- A térkép kitölti a telefon vagy tablet rendelkezésre álló képernyőjét.
- Új `mobile_map_rotation`, `mobile_map_fit` és `mobile_robot_size` beállítások.
- Javítva lett a `contain` megjelenítés +90 és -90 fokos elforgatásnál.
- Kompakt, kétoszlopos mobilvezérlés és 76%-os, görgethető üvegpanel készült.
- Javult az érintőkijelzők felismerése és a rögzített magasságú mobilkártyák
  kezelése.
- Az élő frissítés már nem cseréli le a vezérlőt a lenyomás és a kattintás között.
- Az integráció frontendje és a `/www/anthbot-map` másolata bájtról bájtra azonos.

## Fordítások

- Minden új vezérlés, beállítás, visszajelzés, karbantartási adat, előzmény és
  szegélyszerkesztő szövege elkészült mind a 23 támogatott nyelven.
- Javítva lettek a magyar feliratok, valamint teljessé vált a kézi és
  automatikus zónák fordítása.

## Ellenőrzés

- Mind a 70 automatikus Python regressziós teszt sikeres.
- Minden csomagolt JavaScript-fájl szintaktikai ellenőrzése sikeres.
- A Home Assistant frontendpéldányok bájtról bájtra ellenőrizve vannak.
- A manifestet, a Recorder-kizárásokat és a teljes kiadási ZIP-et a GitHub
  workflow is ellenőrzi.
