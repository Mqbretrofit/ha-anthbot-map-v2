# Anthbot Map v2.4.3-beta.3 – változások

Ez a béta közvetlenül a **v2.4.3-beta.2** verzióra épül, annak meglévő működését megtartva.

## Változások

- Zónánként külön **Nyírási mód** választó:
  - **Normál** → `mow_mode = 0`
  - **Hatékony** → `mow_mode = 1`
- Kikerült a hibás zónás **Szegélynyírás → mow_mode** megfeleltetés.
- A zónabeállításokban alkalmazásszerű **Normál / Hatékony** gombos választó jelent meg.
- Új, reszponzív információs popup magyarázza a két módot.
- A Hatékony mód leírásában külön ki van emelve, hogy **a robot a zóna szegélyét is lenyírja**.
- A magyarázó szöveg mind a 23 támogatott nyelven elérhető.
- Javítva a mobilos gombok összecsúszása, a popup mobilon és asztali gépen egységes sötét megjelenést kapott.
- Frissültek a frontend cache-kulcsok, hogy az új felület és fordítások biztosan betöltődjenek.

## Kompatibilitás

Minden, a v2.4.3-beta.2-ben már működő, ettől független funkció megmarad. A külön tesztág diagnosztikai mow-speed/shadow szenzorai nem kerülnek bele ebbe a kiadásba.
