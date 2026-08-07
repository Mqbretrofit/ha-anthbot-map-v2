# Anthbot Map v1.0.70 – magyar változásnapló

Kiadás dátuma: 2026-08-07

## Újdonságok

- Minden robothoz létrejön egy natív Home Assistant `lawn_mower` entitás.
- A fűnyíró entitásról elindítható a teljes terület nyírása, leállítható az aktuális feladat, és a robot visszaküldhető a töltőre.
- A robot állapota a Home Assistant szabványos állapotaival jelenik meg: nyírás, dokkolva, szüneteltetve, visszatérés és hiba.

> [!CAUTION]
> **Ne használd ezt az integrációt párhuzamosan más Anthbot-integrációval** (például Vincent Verbist vagy Adrian T Ionut integrációjával). Ez dupla entitásokat, egymással versengő felhőkapcsolatokat és ütköző parancsokat okozhat. Frissítés előtt távolítsd el a korábbi Anthbot-integrációt. Az entitásazonosítók megváltozhatnak, ezért az automatizálásokat és a vezérlőpultokat ellenőrizni kell.

## Kompatibilitás

- A meglévő funkciók továbbra is használhatók, többek között a zónanyírás, a kézi és automatikus zónák, a térkép, a szolgáltatások, a gombok, a szenzorok és a kapcsolók.
- Az állapotkezelés támogatja a Genie, M5 és M9 modelleknél előforduló közvetlen, numerikus és beágyazott felhőadat-formátumokat.

## Tesztelés

- Új regressziós tesztek készültek az állapotleképezéshez, az M-sorozat beágyazott állapotaihoz és a hibaállapot elsőbbségéhez.
- A kiadás ellenőrzése egységtesztekkel, HACS-validációval és hassfest ellenőrzéssel történik.
