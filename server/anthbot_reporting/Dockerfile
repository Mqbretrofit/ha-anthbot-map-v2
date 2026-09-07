FROM ghcr.io/home-assistant/base-python:3.13-alpine3.24-2026.06.1

ARG BUILD_VERSION=dev
ARG BUILD_ARCH=local

LABEL \
    io.hass.name="ANTHBOT Reporting Server" \
    io.hass.description="Opt-in telemetry and diagnostics backend for ANTHBOT Map" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANTHBOT_DB_PATH=/data/anthbot_reporting.sqlite3

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app.py ./app.py
COPY asgi.py ./asgi.py
COPY dashboard.html ./dashboard.html
COPY dashboard_login.html ./dashboard_login.html
COPY run.sh /run.sh
RUN chmod a+x /run.sh

EXPOSE 8080

CMD ["/run.sh"]
