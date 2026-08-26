# Anthbot Map v2.4.1-beta

## Beta release

This beta keeps the complete feature set from the v2.4.1 test line while preserving the current main branch changes.

### Battery saver
- Four profiles: Maximum battery care (60–80%), Balanced (65–80%, recommended), Always ready (80–90%), and Custom.
- Keeps the option for installations where the RTK base and charging station share the same smart plug.
- Adds the 55+1 minute anti-shutdown guard while the mower is docked with charger power off.
- Treats `standby` as a valid docked state for the shutdown guard.
- Temporary missing/unknown telemetry no longer kills the guard permanently; it retries after 60 seconds.
- Normal charging takes priority at/below the maintenance threshold.
- Mowing, return-to-dock and other active task states keep station power on.
- Battery saver tile now opens the settings dialog without changing the mode state.
- Battery saver can be enabled/disabled explicitly inside the popup.
- Battery saver profiles and dialog texts remain translated for all 23 supported languages.

### Frontend reliability
- Prevents duplicate registration of the `anthbot-map-card` custom element.
- Prevents duplicate `window.customCards` entries.
- Uses a beta-specific frontend cache key.

### Notes
This is a beta / pre-release build intended for validation before the next stable release.

---

# Anthbot Map v2.4.1-beta – magyar

Ez a béta megtartja a v2.4.1 tesztág teljes funkciókészletét, miközben a jelenlegi `main` változásai sem vesznek el.

### Akkumulátorkímélő mód
- Négy profil: Max. akkukímélés (60–80%), Kiegyensúlyozott (65–80%, ajánlott), Mindig indulásra kész (80–90%) és Egyéni.
- Megmarad a közös RTK/töltő táp beállítás.
- 55+1 perces anti-shutdown védelem dokkolt, kikapcsolt töltőtáp mellett.
- A `standby` állapot most dokkolt/készenléti állapotnak számít a védelemnél.
- Átmeneti hiányzó/ismeretlen telemetria esetén a guard nem áll le végleg, hanem 60 másodperc múlva újrapróbálja.
- A fenntartó töltési szint alatt a normál töltés elsőbbséget kap.
- Nyírás, dokkhoz visszatérés és más aktív feladat esetén a táp bekapcsolva marad.
- A Battery saver csempére kattintás most már csak a beállító ablakot nyitja meg, nem kapcsolja át az állapotot.
- A mód ki-/bekapcsolása külön kapcsolóval történik a felugró ablakban.
- A profilok és a Battery saver ablak szövegei továbbra is mind a 23 támogatott nyelven fordítottak.

### Frontend megbízhatóság
- Dupla `anthbot-map-card` custom element regisztráció elleni védelem.
- Duplikált `window.customCards` bejegyzések kiszűrése.
- Béta-specifikus frontend cache-kulcs.

Ez **béta / előzetes kiadás**, a következő stabil verzió előtti teszteléshez.
