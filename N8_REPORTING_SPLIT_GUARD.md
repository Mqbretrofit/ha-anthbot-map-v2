# N8 branch reporting split guard

`feature/n8-support` must not reintroduce `server/anthbot_reporting` or its CI job.

The integration-side opt-in/reporting client can remain because it talks to the separately maintained reporting backend. Server implementation, add-on metadata and server-only tests belong to the reporting-server repository.
