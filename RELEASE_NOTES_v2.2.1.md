# Anthbot Map v2.2.1

- Fixed outer-edge mowing to use the official app command (`ridable_mow_start`).
- Prevented the selected mowing action from also dispatching a full-area start.
- Kept the robot position updating continuously from MQTT and improved credential recovery.
- Corrected live robot pose priority and heading rendering.
- Added regression coverage for outer-edge start, resume and MQTT recovery.
