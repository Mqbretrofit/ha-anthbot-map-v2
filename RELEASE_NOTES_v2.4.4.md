# Anthbot Map v2.4.4

Stable maintenance release based on the current `test/rain-hold-m-series` build.

## Highlights

- Adds model-neutral rain-hold handling for Genie and M-series task events.
- Keeps the normal mower state as the primary status and shows rain waiting only as a secondary status.
- Removes the unverified rain countdown so the card no longer displays guessed remaining time.
- Refreshes cloud task events immediately after live mower-status transitions, reducing stale `1036`/`1037` event display.
- Makes Battery Saver rain-safe: `1036` and rain-protection rejection `1038` prevent forced mowing resume while rain protection is active.
- Preserves the Shutdown Guard during rain hold and keeps shared RTK power available when configured.
- Fixes the recurring 55+1 minute Shutdown Guard cycle by waiting for the Home Assistant smart-plug state to actually settle to OFF before re-arming the next cycle.
- Improves Genie live mowing-progress target fallback when `last_mowing_task` is unavailable, while preserving the M9/M9 Pro progress behavior.
- Keeps the existing Genie and M-series model-specific control, map, path, zone, history and custom-button functionality from v2.4.3.

## Magyar

- Bekerült a Genie és az M-széria eső miatti várakozásának közös kezelése.
- A fő robotállapot továbbra is elsődleges marad; az eső miatti várakozás csak másodlagos állapotsor.
- Kikerült a nem bizonyítható eső utáni visszaszámlálás, így a kártya nem mutat becsült időt.
- Élő robotállapot-változás után az integráció azonnal frissíti a cloud task eventeket, ezért kisebb az esélye a beragadt `1036`/`1037` állapotnak.
- A Battery Saver esőbiztos lett: `1036` és `1038` esetén nem próbálja erőből folytatni a nyírást.
- Eső miatti várakozás alatt is megmarad a Shutdown Guard működése és a közös RTK-táp kezelése.
- Javítva lett az ismétlődő 55+1 perces Shutdown Guard ciklus: a következő ciklus csak akkor indul újra, amikor a Home Assistant már ténylegesen OFF állapotúnak látja az okoskonnektort.
- Javult a Genie élő nyírási százalékának célterület-felismerése akkor is, ha nincs eltárolt `last_mowing_task`.
- A v2.4.3 meglévő Genie és M-szériás vezérlés-, térkép-, útvonal-, zóna-, előzmény- és egyéni gomb funkciói megmaradnak.
