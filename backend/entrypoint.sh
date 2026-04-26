#!/bin/sh
# Backend boot for Azure Web App for Containers.
# Kept as a real file (not an inline CMD) because Azure's sidecar shell
# wrapper mangles embedded quotes in `sh -c "..."` image CMDs, yielding
# errors like: `alembic: 1: Syntax error: Unterminated quoted string`.

echo "[entrypoint] waiting for postgres and running migrations..."
attempt=0
until alembic upgrade head; do
    attempt=$((attempt + 1))
    echo "[entrypoint] alembic failed (attempt $attempt), retrying in 3s..."
    sleep 3
done
echo "[entrypoint] migrations applied."

echo "[entrypoint] running idempotent seed..."
python -m scripts.seed || echo "[entrypoint] seed step returned non-zero, continuing."

echo "[entrypoint] starting uvicorn on 0.0.0.0:8000..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --proxy-headers
