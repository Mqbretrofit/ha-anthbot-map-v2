# Anthbot Map v1.0.62 – magyar változáslista

## Javítások

- A Home Assistant Recorder többé nem menti el az Anthbot térképszenzor nagy,
  gyorsan változó attribútumait.
- Ezzel megszűnik a 16 384 bájtos állapotattribútum-korlát túllépése és az abból
  eredő felesleges adatbázis-terhelés.
- A térképkártya működése nem változik: az összes szükséges térkép-, útvonal- és
  állapotadat továbbra is élőben elérhető.

## Ellenőrzés

- Új automatikus regressziós teszt biztosítja, hogy az élő térképattribútumok
  Recorder-kizárása teljes maradjon.

## Telepítés

1. Frissítsd az Anthbot Genie Plus integrációt a HACS felületén.
2. Indítsd újra a Home Assistantot.
