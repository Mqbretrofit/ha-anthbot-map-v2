# Anthbot Map v2.4.6-beta.2

Developer test prerelease for uncommon ANTHBOT models.

## New in this beta

- Adds a separate, explicitly opt-in read-only developer test agent.
- The agent can run only pre-installed, whitelisted diagnostic probes; it cannot execute arbitrary code or send mower-control commands.
- Credentials and credential-like fields are filtered before any probe result is uploaded.
- The developer-agent consent is independent from Battery Saver and from the existing usage-statistics / automatic-diagnostics choices.
- The opt-in popup follows the current Home Assistant UI language, with English fallback.
- Adds reporting-server endpoints and a dedicated admin dashboard for pausing/resuming opted-in agents, queuing whitelisted probes, and viewing returned results.
- Reporting Server test package bumped to `1.0.0-test.5`.

## Safety / compatibility

Existing mower control, mapping, progress, Battery Saver, Genie and M-series behaviour is intentionally unchanged. The developer agent is disabled by default and does nothing until an administrator explicitly enables it.

This is a prerelease intended for controlled testing before promotion to a stable version.
