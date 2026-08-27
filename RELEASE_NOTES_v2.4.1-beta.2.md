# Anthbot Map v2.4.1-beta.2

## Battery-saver configuration fix

- Restores the missing `anthbot_map.set_battery_saver_config` backend service
  called by the card's battery-saver dialog.
- Saves the upper charge limit, idle maintenance level, interrupted-task resume
  level, and shared RTK power option persistently in the integration options.
- Applies saved values to the running mower coordinator immediately; a full Home
  Assistant restart is not required.
- When the charging station and RTK use a shared smart plug, power remains on
  during mowing and the start sequence waits for RTK readiness.
- When RTK uses separate power, the charging-station plug may be switched off
  after mowing begins and is switched on again for return and charging.
- Adds regression tests covering the service registration, persistence path,
  frontend/backend parity, and shared-power behavior.

This is a beta / pre-release build intended for validation before the next
stable release.

---

# Anthbot Map v2.4.1-beta.2 – magyar

## Akkumulátorkímélő beállítások javítása

- Visszaállítja a kártya akkumulátorkímélő ablakából meghívott, hiányzó
  `anthbot_map.set_battery_saver_config` backend szolgáltatást.
- Tartósan elmenti a felső töltési határt, a fenntartó töltés indítási szintjét,
  a félbehagyott feladat folytatási szintjét és a közös RTK-táp beállítását.
- A mentett értékeket azonnal alkalmazza a futó koordinátoron; nincs szükség a
  teljes Home Assistant újraindítására.
- Közös töltő-/RTK-okoskonnektornál nyírás közben bekapcsolva tartja a tápot, és
  indulás előtt megvárja az RTK készenlétét.
- Külön RTK-táp esetén nyírás közben kikapcsolhatja a töltőállomás konnektorát,
  visszatéréshez és töltéshez pedig ismét bekapcsolja.
- Regressziós teszteket ad a szolgáltatás regisztrációjához, a tartós mentéshez,
  a frontend/backend egyezéséhez és a közös táp működéséhez.

Ez **béta / előzetes kiadás**, a következő stabil verzió előtti teszteléshez.
