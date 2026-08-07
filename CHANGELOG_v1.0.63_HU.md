# Anthbot Map v1.0.63 – magyar változáslista

## Javítások

- Az AWS IoT STS-hitelesítők lekérése 500, 502, 503, 504, hálózati hiba és
  időtúllépés esetén legfeljebb háromszor próbálkozik, 1 és 3 másodperces
  várakozással.
- Az integráció csak valódi, 401/403-as hitelesítési hibánál jelentkezik be újra
  az Anthbot-fiókba. Az Anthbot felhő 500/502-es hibája ezért nem indít
  felesleges bejelentkezéseket.
- Ha a korai frissítés átmenetileg sikertelen, a még ténylegesen le nem járt
  gyorsítótárazott IoT-hitelesítő a lejáratáig használható marad.
- Lejárt vagy az AWS által már elutasított hitelesítő nem kerül újra
  felhasználásra.
- Az egyes átmeneti próbálkozások csak debug szinten kerülnek a naplóba; warning
  bejegyzés a próbálkozások kimerülése után készül.
- A `hacs.json` ismét megfelel a jelenlegi HACS-sémának, és az integráció
  tartalmazza a HACS által elvárt helyi márkaikont.

## Ellenőrzés

- Automatikus regressziós tesztek ellenőrzik az átmeneti hibák újrapróbálását,
  a 401/403 utáni egyszeri újrabejelentkezést, a még érvényes gyorsítótár
  használatát és a lejárt vagy elutasított hitelesítők tiltását.
- A GitHub ellenőrzési munkafolyamata minden pushnál és pull requestnél
  automatikusan lefuttatja a teszteket.

## Telepítés

1. Frissítsd az Anthbot Genie Plus integrációt a HACS felületén.
2. Indítsd újra a Home Assistantot.
