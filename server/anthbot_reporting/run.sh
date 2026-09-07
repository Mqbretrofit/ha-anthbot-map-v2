#!/usr/bin/with-contenv bashio
set -euo pipefail

export ANTHBOT_DB_PATH="/data/anthbot_reporting.sqlite3"
export ANTHBOT_ADMIN_TOKEN="$(bashio::config 'admin_token')"

bashio::log.info "Starting ANTHBOT Reporting Server on port 8080"
exec uvicorn app:app \
  --host 0.0.0.0 \
  --port 8080 \
  --proxy-headers \
  --no-access-log
