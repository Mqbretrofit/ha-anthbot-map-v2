# Anthbot Map v2.4.3-beta.2

## Multi-mow learned zone progress

This beta is based on the complete v2.4.3-beta.1 code and preserves all existing features.

- Keeps the geometric `Active zone area` unchanged.
- Lets progress use a learned effective mowing area per zone selection.
- Uses the median of the last 3 cloud-confirmed completed mowings (`1014` event).
- One sample provides a provisional reference; 3 samples make it stable.
- Intermediate charging, rain return, low-battery return, manual docking, and interrupted tasks are not learned.
- Learned samples survive Home Assistant restarts and integration reloads.
- Falls back to the v2.4.3-beta.1 polygon/No-Go calculation until a learned sample exists.
- Applies the matching learned reference to both live and mowing-history progress.
- Exposes the learned reference, samples, count, and confidence in progress sensor attributes.
