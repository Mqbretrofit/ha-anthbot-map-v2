# Anthbot Map v2.4.5-beta.3

## Performance fix

- Stops the Battery Saver `rain_hold` state from polling the cloud task-event REST endpoint on every coordinator update while the mower is stably docked.
- Keeps immediate rain-stop/resume handling: when the mower leaves the docked phase, the existing live MQTT status transition still triggers an immediate task-event refresh.
- Keeps the normal coordinator task-event refresh as a fallback, so cloud event history is still updated without rapid polling.
- Preserves the v2.4.5-beta.2 MQTT duplicate filtering, path/progress caches, rain handling, Battery Saver and Shutdown Guard behavior.

## Magyar

- Javítva a Genie-nél mért felesleges task-event REST lekérdezés: stabil, dokkolt `rain_hold` állapotban a Battery Saver már nem kérdezi le az eseménylistát minden coordinator frissítésnél.
- Az eső utáni folytatás továbbra is azonnal reagál: amikor a robot kilép a dokkolt állapotból, a meglévő MQTT státuszváltás azonnali task-event frissítést indít.
- A normál coordinator frissítés tartalék megoldásként továbbra is frissíti az eseménylistát.
- A beta.2 összes optimalizációja és működő funkciója változatlanul megmarad.
