# Anthbot Map v2.0.0-beta.12 – magyar változásnapló

- A térképkártya kihagyja a YAML-ban megadott, de `unavailable` állapotú
  kapcsolódó entitásokat, és automatikusan az aktív számozott vagy számozatlan
  Anthbot-entitást választja.
- Az indítás, leállítás, dokkolás és zónanyírás automatikusan a működő natív
  Home Assistant gombentitást használja.
- A tartalék szolgáltatáshívás az új `anthbot_map` és a régi
  `anthbot_genie_plus` integrációval is működik.
- Az integráció automatikusan a `/config/www/anthbot-map-v2/` mappába tükrözi
  a kártyát, ezért az a v2 bejegyzés letiltása után, a régi integráció
  tesztelésekor is betöltődik.
