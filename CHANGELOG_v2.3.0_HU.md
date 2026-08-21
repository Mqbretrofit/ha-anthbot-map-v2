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
- Az eltolás, a vízszintes és függőleges méretezés, valamint a forgatás már a
  teljes nyírási útvonalra, lefedettségre és robotpozícióra hat, nem csak a
  robotikonra.
- A robotikon iránya a nyírási útvonal illesztésétől külön állítható.
- A nem négyzetes térképek forgatása többé nem torzítja el az alakzatot.

## Megbízhatóság és adatvédelem

- Több robot esetén is a megfelelő robot nyírási részlete töltődik le.
- A hosszú nyírási időket nem téveszti össze ezredmásodperces értékekkel.
- A rögzített eszközazonosítók kikerültek a forrásból.
- A frontend másolatai és a kiadási verziók egységesek.
- Kikerült a töltőérintkező-karbantartás szolgáltatás duplikált `serial_number`
  mezője, és regressziós teszt védi a YAML-fájlokat a hasonló hibáktól.
