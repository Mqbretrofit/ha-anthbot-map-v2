# Anthbot Map v2.4.5-beta.1

Runtime diagnostics prerelease for investigating unusually high Home Assistant CPU usage.

## What's new

- Adds lightweight per-mower runtime activity counters without creating a new continuously updating entity.
- Exposes a `runtime_performance` diagnostic block on the existing Map entity.
- Tracks MQTT shadow updates, coordinator updates, REST refreshes, task-event refreshes/downloads, M-series path merges, mowing-progress evaluations and estimated entity writes per minute.
- Logs one compact runtime summary per minute at DEBUG level during normal activity.
- Emits a WARNING with `[HIGH ACTIVITY]` only when runtime activity exceeds the diagnostic thresholds.
- Keeps the diagnostics out of Recorder history so the diagnostic block itself does not add database load.
- Contains the complete v2.4.4 functionality; this beta is intended only to help identify model/data-specific high-CPU cases.

## Magyar

Ez a prerelease a szokatlanul magas Home Assistant CPU-terhelés kivizsgálására készült.

- Robotenként könnyű futásidejű aktivitásszámlálókat ad hozzá új, folyamatosan frissülő entitás nélkül.
- A meglévő Map entitásban megjelenik a `runtime_performance` diagnosztikai blokk.
- Számolja többek között az MQTT shadow frissítéseket, coordinator frissítéseket, REST lekéréseket, task-event frissítéseket, M-szériás path merge műveleteket, progress-számításokat és a becsült entitásírásokat percenként.
- Normál esetben percenként egy rövid DEBUG összesítést ír.
- Csak túlzott aktivitásnál ír `[HIGH ACTIVITY]` WARNING sort.
- A diagnosztikai blokk nincs Recorderben tárolva, így maga a mérés nem növeli érdemben az adatbázis-terhelést.
- A v2.4.4 teljes működését tartalmazza; ez a beta kizárólag diagnosztikai tesztverzió.
