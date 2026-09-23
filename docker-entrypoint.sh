#!/bin/sh
set -eu

python - <<'PY'
import os
import time
import mysql.connector

host = os.getenv("MYSQL_HOST", "mysql")
port = int(os.getenv("MYSQL_PORT", "3306"))
user = os.getenv("MYSQL_USER", "root")
password = os.getenv("MYSQL_PASSWORD", "Sakthi@582")

for attempt in range(1, 61):
    try:
        conn = mysql.connector.connect(host=host, port=port, user=user, password=password)
        conn.close()
        print("MySQL is ready.")
        break
    except mysql.connector.Error as exc:
        print(f"Waiting for MySQL ({attempt}/60): {exc}")
        time.sleep(2)
else:
    raise SystemExit("MySQL did not become ready in time.")
PY

python database.py
exec gunicorn --bind 0.0.0.0:5000 --workers "${GUNICORN_WORKERS:-2}" --timeout 120 app:app
