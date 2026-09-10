# Reporting server moved

The ANTHBOT reporting server/add-on is maintained in a separate repository.

This integration repository intentionally contains only the Home Assistant integration/client-side reporting code and its tests. The server implementation and server-specific CI do not belong here anymore.

The `server/anthbot_reporting` tree and the Home Assistant Apps repository metadata were removed from `feature/n8-support` to keep N8 validation focused on the integration itself.
