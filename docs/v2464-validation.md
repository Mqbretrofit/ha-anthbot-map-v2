# v2.4.6.4 validation checklist

- M9 Pro: an unchanged `_no_go_path_check` must not create hourly duplicate reports.
- M9 Pro: a historical cloud `code_type=error` event older than 15 minutes must be marked stale and must not independently trigger a new automatic error report.
- Genie 1000/3000: the live-shadow listener must continue reconnecting after PING timeout, WebSocket close/reset, and unexpected normal runtime transport exceptions.
- Genie 1000/3000: after three consecutive reconnect failures, force one fresh STS credential acquisition before continuing retries.
- M5/M9: map-manager archive naming remains `map_manager_<serial>.tar.gz`; logical map id is never used as an archive filename.
- M5/M9: diagnostics expose separate live/logical map id and embedded raster map id.
- N8: no M-series map identity guard is widened to N8.
