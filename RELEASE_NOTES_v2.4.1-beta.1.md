# Anthbot Map v2.4.1-beta.1

## Integration reload fix

- Fixes an exception during config-entry unload caused by two obsolete service
  names left in the service cleanup list.
- The Anthbot Map integration can now be reloaded without requiring a full
  Home Assistant restart.
- Entity platforms are unloaded before the MQTT listener and battery-saver
  background tasks are stopped, preventing a failed platform unload from
  leaving the integration partially stopped.
- Adds regression coverage for service cleanup and unload ordering.

This is a beta / pre-release build intended for validation before the next
stable release.

---

# Anthbot Map v2.4.1-beta.1 – magyar

## Integráció-újratöltési javítás

- Javítja a konfigurációs bejegyzés leállításakor jelentkező kivételt, amelyet
  két, a szolgáltatástakarítási listában maradt, már nem létező szolgáltatásnév
  okozott.
- Az Anthbot Map integráció mostantól a teljes Home Assistant újraindítása
  nélkül is újratölthető.
- Az entitásplatformok az MQTT-figyelő és az akkukímélő háttérfolyamatok
  leállítása előtt töltődnek ki, így egy sikertelen platformleállítás nem hagyja
  fél-leállított állapotban az integrációt.
- Regressziós tesztek kerültek be a szolgáltatások takarítására és a helyes
  leállítási sorrendre.

Ez **béta / előzetes kiadás**, a következő stabil verzió előtti teszteléshez.
