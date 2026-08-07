# Anthbot Map v2.0.0-beta.5 – magyar változásnapló

## Kritikus javítás

- Javítva a `TrackerEntity` import kompatibilitása. A béta.2–4 emiatt egyes
  Home Assistant verziókon nem tudta betölteni az `anthbot_map` integrációt.
- Az integráció most az új importútvonalat használja, ahol az elérhető, és
  automatikusan visszaáll a régi, kompatibilis útvonalra.
