# Anthbot Map v2.4.1-beta.4

## Battery saver reliability fix

- Keeps the Battery saver settings tile as a popup opener only; it does not toggle the mode directly.
- Keeps the enlarged Battery saver enable/disable checkbox inside the popup.
- Keeps the persistent `anthbot_map.set_battery_saver_config` backend service and shared RTK power settings.
- Restores normal charger power before Battery saver mode is disabled, so the configured charging-station smart plug is switched back on immediately when the mode is turned off.
- Preserves the 55+1 minute anti-shutdown guard, `standby` handling, normal maintenance charging, and mowing/RTK power behavior.
- The release workflow verifies the full test suite, JavaScript syntax, frontend mirrors, Battery saver popup UI, backend service presence, and charger-restore ordering before publishing.

This is a beta / pre-release build intended for validation before the next stable release.

---

# Anthbot Map v2.4.1-beta.4 – magyar

## Akkumulátorkímélő mód megbízhatósági javítása

- A Battery saver beállítási csempe továbbra is csak a popupot nyitja meg; közvetlenül nem kapcsolja a módot.
- A nagyobb Battery saver ki-/bekapcsoló jelölőnégyzet a popupban marad.
- Megmarad a tartós `anthbot_map.set_battery_saver_config` backend szolgáltatás és a közös RTK-táp beállítás.
- Battery saver kikapcsolásakor a rendszer előbb visszaállítja a normál töltőtápot, ezért a konfigurált töltőállomás-okoskonnektor azonnal visszakapcsol.
- Megmarad az 55+1 perces anti-shutdown védelem, a `standby` kezelés, a normál fenntartó töltés és a nyírás/RTK tápkezelés.
- A kiadási workflow publikálás előtt ellenőrzi a teljes tesztkészletet, a JavaScript szintaxist, a frontend tükrök egyezését, a Battery saver popup felületét, a backend szolgáltatást és a töltő-visszakapcsolás helyes sorrendjét.

Ez **béta / előzetes kiadás**, a következő stabil verzió előtti teszteléshez.
