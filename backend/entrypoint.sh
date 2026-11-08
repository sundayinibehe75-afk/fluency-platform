#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
# --proxy-headers: take the visitor's IP from X-Forwarded-For (set by the
# Nginx proxy). The API port is only reachable inside the Docker network, so
# only the proxy can set that header.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
