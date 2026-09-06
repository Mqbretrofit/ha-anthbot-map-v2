# Anthbot Map v2.4.5-beta.2

Performance-optimization prerelease built on v2.4.5-beta.1 diagnostics.

## What changed

- Suppresses MQTT shadow fields/messages only when the incoming value is exactly unchanged from the current or already-pending state.
- Keeps real MQTT telemetry immediate; no polling interval is increased and no mower command is delayed.
- Coalesces cloud task-event refreshes by real task phase instead of reacting to charge/idle/sleep/standby status chatter.
- Performs the 5.2-second task-event retry only when the first REST event list has not yet caught up with the live task transition.
- Caches M-series merged mowing paths until path points, path id, angle or relevant metadata really change.
- Caches expensive mowing-progress zone/no-go geometry within unchanged state geometry.
- Reuses validated Map path lists and cached path-type counts instead of rebuilding/copying large path lists for every entity write.
- Extends `runtime_performance` with an `optimization` block showing duplicate MQTT suppression, conditional task-event retries, path-merge cache hits and progress-geometry cache effectiveness.
- Contains all v2.4.4 functionality plus the v2.4.5-beta.1 runtime diagnostics.

## Magyar

Ez a tesztverzió a CPU- és memóriaigény csökkentésére készült úgy, hogy a valós idejű működés ne lassuljon.

- Csak a ténylegesen változatlan MQTT shadow mezőket/üzeneteket dobja el.
- A valódi MQTT állapotváltozások továbbra is azonnal feldolgozásra kerülnek.
- A Genie task-event REST frissítés csak valódi feladatfázis-váltásra reagál; a töltés/készenlét/alvás közötti zaj nem indít felesleges lekéréseket.
- Az 5,2 másodperces task-event újrapróbálás csak akkor fut le, ha az első REST válasz még nem tartalmazza a friss eseményt.
- Az M5/M9 nyírási útvonal összeállítása cache-t kapott, ezért változatlan útvonalnál nem épül újra a teljes pontlista.
- A progress zóna/no-go geometria számítása változatlan geometriánál cache-ből történik.
- A Map entitás nagy útvonallistáját nem másolja újra minden állapotfrissítéskor, és a ponttípus-számítás is cache-elt.
- A `runtime_performance` új `optimization` blokkja megmutatja, mennyi felesleges munka lett elkerülve.
- A v2.4.4 teljes funkcionalitását és a v2.4.5-beta.1 diagnosztikáját is tartalmazza.
