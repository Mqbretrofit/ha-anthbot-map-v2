# Anthbot Map v2.4.5-beta.4

## Performance fix

- Fixes the remaining Genie task-event REST polling loop observed in `v2.4.5-beta.3`.
- The `manual_charge` Battery Saver phase is now a short cloud-propagation grace period: it performs one delayed task-event recheck, then settles to the correct long-lived phase instead of polling on every coordinator update.
- A delayed 1021/1036/1014 event can still classify the return as low-battery recovery, rain hold, or completed task.
- Stable rain-hold suppression also treats the Genie `shutdown` status as a quiet docked/powered-off state, without changing the global docked-state semantics used by other Battery Saver logic.
- Preserves all `v2.4.5-beta.3` MQTT filtering, path/progress caches, rain handling, Battery Saver and Shutdown Guard behavior.

## Magyar

- Javítva a `v2.4.5-beta.3` után is megmaradt Genie task-event REST lekérdezési ciklus.
- A Battery Saver `manual_charge` állapota most csak rövid felhő-szinkronizációs türelmi állapot: egyetlen késleltetett task-event ellenőrzést végez, majd normál állapotba vált, így nem kérdezi le az eseménylistát minden coordinator frissítésnél.
- A késve megjelenő 1021/1036/1014 esemény továbbra is helyesen felismerhető alacsony akkus visszatérésként, eső miatti várakozásként vagy befejezett feladatként.
- Stabil eső miatti várakozásnál a Genie `shutdown` státuszát is csendes dokkolt/kikapcsolt állapotként kezeljük kizárólag a felesleges event polling szűrésénél; a többi Battery Saver logikát nem változtatjuk meg.
- A beta.3 összes meglévő optimalizációja és működő funkciója megmarad.
