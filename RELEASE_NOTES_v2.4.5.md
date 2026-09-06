# Anthbot Map v2.4.5

## Performance and stability

- Promotes the tested `v2.4.5-beta.4` code to stable without adding new mower-control behavior.
- Adds low-overhead runtime activity diagnostics on the existing Map entity for support investigations; the diagnostic attribute is excluded from Recorder history.
- Filters repeated identical MQTT shadow fields/messages before they trigger unnecessary Home Assistant work while preserving real telemetry changes.
- Caches expensive M-series path assembly and mowing-progress geometry so unchanged map/path data is not rebuilt on every coordinator update.
- Coalesces task-event refreshes around real task-phase transitions instead of cosmetic status chatter.
- Fixes the Genie task-event REST polling loop: stable operation no longer downloads the task-event list every few seconds.
- Makes `manual_charge` a short cloud-propagation grace state with one delayed event recheck, then settles to the correct long-lived Battery Saver phase.
- Keeps delayed `1021`, `1036`, `1037`, `1038` and `1014` task-event handling intact for low-battery recovery, rain hold/resume and task completion.
- Keeps the Genie `shutdown` state quiet for rain-hold polling suppression without changing the global docked-state rules used by the rest of Battery Saver.
- Preserves the existing rain handling, Battery Saver, recurring Shutdown Guard, Genie/M-series model separation, map/path/zone/history support and custom controls from 2.4.4.

## Validation

- Tested with ANTHBOT Genie 1000 and M9 Pro hardware.
- Runtime diagnostics showed stable task-event downloads at zero per minute during normal idle operation after the fix.
- 120-second Home Assistant profiler tests showed no Anthbot runaway/busy loop on either the main test system or Home Assistant Green.

## Magyar

- A tesztelt `v2.4.5-beta.4` kód stabil kiadása, új robotvezérlési viselkedés hozzáadása nélkül.
- Bekerült az alacsony többletterhelésű futásidejű aktivitásdiagnosztika a meglévő Map entitásba; a változó diagnosztikai attribútumot a Recorder nem tárolja.
- Az azonos MQTT shadow mezőket és teljesen ismétlődő üzeneteket az integráció kiszűri, mielőtt felesleges Home Assistant feldolgozást indítanának; a valódi telemetria-változások továbbra is azonnal átmennek.
- Cache került az M-szériás útvonal-összeállítás és a nyírási százalék geometriája elé, így változatlan adatoknál nincs újraszámítás minden coordinator frissítéskor.
- A task-event frissítés valódi feladatfázis-váltásokhoz igazodik, nem a jelentéktelen státuszcsevegéshez.
- Javítva lett a Genie task-event REST lekérdezési ciklusa: normál stabil állapotban már nem tölti le néhány másodpercenként az eseménylistát.
- A `manual_charge` most rövid felhő-szinkronizációs türelmi állapot, egyetlen késleltetett eseményellenőrzéssel, majd a megfelelő tartós Battery Saver fázisba lép.
- A késve érkező `1021`, `1036`, `1037`, `1038` és `1014` események kezelése megmaradt az alacsony akkus visszatéréshez, eső miatti várakozáshoz/folytatáshoz és feladatbefejezéshez.
- A Genie `shutdown` állapota kizárólag a rain-hold polling szűrésénél számít csendes állapotnak; a Battery Saver többi dokkoltállapot-logikája változatlan.
- Megmaradt a 2.4.4 összes működő esőkezelése, Battery Saver funkciója, ismétlődő Shutdown Guardja, Genie/M-széria modellkülönválasztása, térkép-, útvonal-, zóna-, előzmény- és egyéni vezérlése.

## Ellenőrzés

- Közvetlenül tesztelve ANTHBOT Genie 1000 és M9 Pro hardveren.
- A javítás után normál nyugalmi állapotban a futásidejű diagnosztika 0 task-event letöltést mutatott percenként.
- 120 másodperces Home Assistant profiler teszteken sem a fő tesztrendszeren, sem Home Assistant Greenen nem látszott Anthbot runaway/busy loop.
