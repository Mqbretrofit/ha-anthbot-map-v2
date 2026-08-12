# Anthbot Map v2.0.0

## Első stabil v2 kiadás

A `v2.0.0` a valós roboton kipróbált `v2.0.0-beta.15` forrás stabil
kiadása. Az integráció programkódja nem változott a tesztelt béta óta.

## Kiemelt fejlesztés: gyorsabb AWS IoT/MQTT élő kapcsolat

- Tartós AWS IoT MQTT-over-WebSocket shadow-kapcsolat került az integrációba,
  ezért a robot állapota, pozíciója, iránya és töltöttsége lényegesen gyorsabban
  frissülhet, mint kizárólag időzített HTTP-lekérdezésekkel.
- A robotparancsok elsőként az aktív MQTT-kapcsolatot használják; ha ez nem
  érhető el, az integráció automatikusan a hitelesített AWS IoT HTTP publish
  végpontra vált vissza.
- Korlátozott újracsatlakozás, fiók-újrahitelesítés és rövid élettartamú STS
  hitelesítőadat-frissítés került bele. Az aláírt URL-ek és titkos adatok nem
  kerülnek a naplóba.
- A gyorsan érkező shadow-frissítések összevonva kerülnek a Home Assistantba,
  így elkerülhető a korai teszt során tapasztalt WebSocket-üzenetáradat.
- Aktív MQTT mellett ötpercenkénti biztonsági HTTP-egyeztetés, kapcsolat nélkül
  pedig konzervatív, egyperces HTTP-tartalékfrissítés marad működésben.
- A térképentitás diagnosztikája és a mellékelt térképkártya jelzi az MQTT
  online/offline állapotát.
- Bekerült a térképfájlok integritás-ellenőrzése, a frissítési diagnosztika és
  a biztonságosan kitakart Home Assistant diagnosztikai export.

Ez a kiadás a valós roboton kipróbált `test27` csomagból készült. A külön
kiadott magyar hangcsomag szándékosan nincs benne.

> Egyszerre csak egy Anthbot-integráció legyen engedélyezve. A régi integráció
> telepítve maradhat a gyors visszaállításhoz, de váltáskor indítsd újra a Home
> Assistantot.
