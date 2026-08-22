# Anthbot Map v2.3.0

## Nyírási előzmények

- Az integráció a mobilalkalmazás igazolt nyírási-előzmény végpontját használja.
- Az előzmények áttekinthető kártyákon mutatják a területet, folyamatot,
  időtartamot, nyírási módot, indítási forrást és zónákat.
- Egy nyírás megnyitásakor megjelenik a hozzá tartozó terület-, térkép- és
  útvonalrészlet.
- Elérési út: **Anthbot Map kártya → Diagnosztika → Korábbi nyírási
  feladatok**; egy befejezett nyírásra kattintva nyílik meg a részletes nézet.
- Javítva lett a történeti MGS v1 útvonal koordinátaskálája.
- Az ismert, kikapcsolt késsel megtett útvonalszakaszok nem jelennek meg
  lenyírt területként.

## M5/M9 kompatibilitás

- Valós M9 adatok alapján elkészült a property-shadow és az élő `curpath`
  kísérleti feldolgozása.
- Javult az állapot-, hiba-, parancs-, térképarchívum-feldolgozás és
  ébresztéskezelés úgy, hogy a Genie útvonalai változatlanok maradnak.
- **Ismert korlátozás:** az M5/M9 modelleknél a térképes megjelenítés még nem
  működik.

## Térképillesztés

- A félreérthető **Robot illesztése** elnevezés helyett **Nyírási útvonal
  illesztése** jelenik meg.
- Az eltolás, a vízszintes és függőleges méretezés, valamint a forgatás a teljes
  nyírási útvonalra és lefedettségre hat, a robotikontól függetlenül.
- A robot és a nyírási útvonal külön kalibrációs kezelőszerveket és külön YAML
  blokkot kapott.
- A fel, le, balra, jobbra, keskenyebb, szélesebb, alacsonyabb és magasabb
  kezelőszervek minden külön kalibrálható réteget a térképillesztéssel azonos
  vizuális irányba mozgatnak.
- A robotikon iránya a nyírási útvonal illesztésétől külön állítható.
- A felhőből érkező robotirány vízszintes mozgásnál már nem tükrözött, miközben
  a függőleges mozgás korábban helyes iránya megmaradt.
- A korábbi `robotCalibration.rotation` továbbra is csak az ikon irányát
  korrigálja; az útvonal külön forgatása a `mowingPathCalibration` blokkba kerül.
- A nyírási útvonal forgatása nem torzítja el az alakzatot nem négyzetes
  térképen sem, miközben a korábbi térképkalibráció működése változatlan marad.

## Megbízhatóság és adatvédelem

- Több robot esetén is a megfelelő robot nyírási részlete töltődik le.
- A hosszú nyírási időket nem téveszti össze ezredmásodperces értékekkel.
- A rögzített eszközazonosítók kikerültek a forrásból.
- A parancs-visszaigazolás megmaradt frontend debug naplózása is kikerült.
- A kalibráció és a nyírási előzmények szövege mind a 23 támogatott nyelven
  teljes, angol tartalékfeliratok nélkül.
- A frontend másolatai és a kiadási verziók egységesek.
- Kikerült a töltőérintkező-karbantartás szolgáltatás duplikált `serial_number`
  mezője, és regressziós teszt védi a YAML-fájlokat a hasonló hibáktól.
