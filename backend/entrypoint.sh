#!/bin/sh
# Backend boot for Azure Web App for Containers.
# Kept as a real file (not an inline CMD) because Azure's sidecar shell
# wrapper mangles embedded quotes in `sh -c "..."` image CMDs, yielding
# errors like: `alembic: 1: Syntax error: Unterminated quoted string`.

echo "[entrypoint] waiting for postgres and running migrations..."

# Guard: if the DB is stamped at a revision whose file no longer exists
# (e.g. 005_production_records or 007_production_batches were removed),
# reset the stamp to the nearest known-good head so alembic upgrade can proceed.
python - << 'PYEOF'
import os, sys
try:
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ.get("DATABASE_URL_SYNC", ""))
    known = {
        None, "001_initial", "002_var_mat_req", "003_user_discount",
        "004_order_materials_deducted", "006_order_item_fulfillment",
        "007_production_batches", "008_activity_log_columns",
        "010_batch_partial_outcome", "011_order_stock_deducted",
        "012_extend_user_roles",
    }
    with engine.begin() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        current = row[0] if row else None
        if current not in known:
            conn.execute(text("UPDATE alembic_version SET version_num = '006_order_item_fulfillment'"))
            print(f"[entrypoint] migration guard: stamped {current!r} -> 006_order_item_fulfillment", flush=True)
except Exception as exc:
    print(f"[entrypoint] migration guard skipped: {exc}", file=sys.stderr, flush=True)
PYEOF

attempt=0
until alembic upgrade head; do
    attempt=$((attempt + 1))
    echo "[entrypoint] alembic failed (attempt $attempt), retrying in 3s..."
    sleep 3
done
echo "[entrypoint] migrations applied."

# Bootstrap the least-privilege runtime DB user (art_app). Idempotent.
# Connects as the server admin via DATABASE_URL_SYNC and (re)applies
# grants + rotates the password from ART_APP_DB_PASSWORD. Skips silently
# when those env vars are not set (docker-compose dev path).
#
# If bootstrap fails when the env vars ARE set, exit non-zero — uvicorn
# would then immediately fail to authenticate as art_app, so it is safer
# to refuse to boot than to flap on connection errors.
echo "[entrypoint] bootstrapping art_app DB role..."
if ! python -m scripts.bootstrap_db_user; then
    echo "[entrypoint] bootstrap_db_user failed; refusing to start uvicorn." >&2
    exit 1
fi

echo "[entrypoint] running idempotent seed..."
python -m scripts.seed || echo "[entrypoint] seed step returned non-zero, continuing."

echo "[entrypoint] starting uvicorn on 0.0.0.0:8000..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --proxy-headers
