# Anthbot Map v2.0.0-beta.14 – magyar változásnapló

## Javítva

- A „parancs elküldve” visszajelzés most azonnal, még a Home Assistant
  szolgáltatáshívás befejezése előtt megjelenik.
- Az egyéni `button_actions` műveletek is ugyanazt az elküldési,
  visszaigazolási, időtúllépési és hibajelzési folyamatot használják.
- Az üzenet fix, magas rétegszintű kártyaértesítésként jelenik meg, ezért panel
  irányítópulton és mobil elrendezésben sem kerül más elemek mögé.

## Telepítés

A gyorsítótár-paraméter nélküli erőforrás továbbra is használható:

```text
/anthbot-map-v2/anthbot-map-card.js
```

HACS-frissítés után indítsd újra a Home Assistantot, majd frissítsd kényszerítve
az oldalt vagy indítsd újra a mobilalkalmazást.
