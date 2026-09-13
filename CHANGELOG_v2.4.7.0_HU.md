# ANTHBOT Map 2.4.7.0 – változások

Ez a kiadás a 2.4.6.6 stabil alapjára és a terepen ellenőrzött 2.4.6.7 stabilitási javításokra épülő architekturális és stabilitási frissítés.

## Élő térkép architektúra

- A nagy frekvenciájú live map/path/pose adatfolyam leválik a Home Assistant entity state mechanizmusáról.
- Külön Home Assistant WebSocket transport kezeli az élő térképadatot.
- A kártya első csatlakozáskor teljes snapshotot kap, utána pedig csak path deltákat, nem a teljes útvonalat újra és újra entity attribútumként.
- Sequence kezelés, automatikus resync, path-id váltás és hosszú M-series útvonalaknál gördülő path-ablak támogatás került bele.
- Ha a live frontend erőforrás nem használható, a rendszer kompatibilitási módban megtartja a régi entity-alapú térképadatot.
- Downgrade után egy bent maradó régi frontend resource nem veheti át a működést, ha a backend már nem jelzi a live-stream támogatást.
- Live-stream módban a kártya leállítja a régi periodikus `homeassistant.update_entity` Map-entity pollingot.

## Home Assistant Recorder és state terhelés

- WebSocket live módban a Map entity már csak kompakt státusz/diagnosztikai anchor; a teljes `path`, `cloud_path`, `mowed_path` és `pose` geometria nem kerül bele.
- A map archive selection, task-event history, error-history snapshot és más forgó diagnosztikai gyűjtemények már nem indítanak néhány másodpercenként új Map state write-ot.
- A live transport indulásakor a már korábban regisztrált Map coordinator listenerek is átállnak a kompakt write-semantics logikára, így a régi Recorder wrapper sem tud tovább a korábbi gyakorisággal írni.
- A `runtime_performance` továbbra is elérhető élő diagnosztikához, de nem kerül Recorder attribútumként eltárolásra.
- Egyperces heartbeat frissíti a nem sürgős Map diagnosztikát úgy, hogy az élő nyírás ne okozzon Recorder churnt.

## No-Go és event-loop stabilitás

- A drága No-Go geometriai ellenőrzés kikerült a Home Assistant event loopból, és `async_add_executor_job()` segítségével executorban fut.
- A védelem az M-series, N8 és Genie path diagnosztikára is kiterjed.
- Stabil geometry/path revision cache és live cadence védi a rendszert attól, hogy változatlan geometriát minden cloud update-nél újra teljesen végigszámoljon.
- A path/pose továbbítás és a robotvezérlési command routing nem változott.

## Terepi ellenőrzés

A live-map architektúrát valódi Anthbot M9 Pro roboton, aktív nyírás közben ellenőriztük:

- a live path és a robot pozíciója WebSocketen tovább frissült;
- a Home Assistant Map entityben nem volt teljes path/pose geometria, miközben az útvonal tovább nőtt;
- a Recorder terhelése a korábbi több tíz Map state / 3 perc értékről 3 state sorra csökkent egy 3 perces aktív nyírási mérésben;
- Home Assistant restart után a teljes korábbi útvonal WebSocket reconnect/snapshot segítségével visszatért;
- a mozgás, pause/resume és restart működése megmaradt;
- a tesztelt folyamatban nem jelent meg ANTHBOT event-loop blokkolás vagy startup bootstrap timeout.

Automatikus tesztek védik a WebSocket snapshot/delta protokollt, resync viselkedést, rolling-window path kezelést, compact entity architektúrát, meglévő listener újrakötést, legacy polling letiltást, Recorder szemantikát, M-series/N8 No-Go throttlingot és Genie path diagnosztikát. A release candidate-en a Home Assistant hassfest és HACS ellenőrzések is sikeresek.

## Modellhatókör

- M9 Pro: a live transport és Recorder működés valódi eszközön terepen ellenőrizve.
- M5/M9 család: ugyanazt a védett M-series path implementációt használja.
- N8: a külön N8 model path/control kezelés megmarad; a No-Go executor védelem és N8-specifikus regressziós tesztek benne vannak.
- Genie: a külön path diagnosztika megmarad; a drága No-Go számítás executorba került és tesztek védik.

## Hatókörvédelem

Ez a kiadás nem módosítja a robotvezérlési command routingot. A Genie, M5/M9 család és N8 vezérlési útvonalai továbbra is külön maradnak. A külön `Mqbretrofit/anthbot-reporting-server` projektet ez a kiadás nem módosítja.
