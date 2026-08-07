# Anthbot Map v2.0.0-beta.7 – magyar változásnapló

## Vezérlési javítás

- A teljes nyírás, leállítás, töltőre küldés és zónanyírás automatikus módban
  közvetlenül az `anthbot_map` integráció szolgáltatásain keresztül fut.
- A zónanyírás a térképből kapott valódi `100/101/102` zónaazonosítót adja át.
- Natív Home Assistant gombentitást csak kifejezett YAML `controls` beállítás
  esetén használ a kártya.
