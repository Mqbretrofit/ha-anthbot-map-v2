# Anthbot Map v1.0.69 – változások

## M9 akkumulátorszenzor javítása

- Az M9 `elec.value.value` formátumú, időbélyeges akkumulátoradata helyesen százalékértékké alakul.
- A régi Genie `elec: 85`, az M5 `elec: {"value": 85}` és az M9 kétszeresen beágyazott formátuma egyaránt támogatott.
- A feldolgozás hibás, hiányzó, ciklikus vagy 0–100 tartományon kívüli adatnál biztonságosan `None` értéket ad.

## Tesztek

- Új regressziós tesztek fedik le mindhárom ismert akkumulátorformátumot és a hibás bemeneteket.
