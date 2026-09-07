FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANTHBOT_DB_PATH=/data/anthbot_reporting.sqlite3

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./app.py

RUN useradd --create-home --uid 10001 anthbot \
    && mkdir -p /data \
    && chown -R anthbot:anthbot /app /data

USER anthbot
VOLUME ["/data"]
EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-access-log"]
