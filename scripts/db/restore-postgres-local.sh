#!/usr/bin/env bash
# Restore a custom-format pg_dump file into the LOCAL docker-compose
# PostgreSQL service. Hard-coded to local; refuses any remote target.
#
# Usage (from repo root):
#   ./scripts/db/restore-postgres-local.sh backups/postgres/art-dev-postgres-2026-05-04-1530.dump
#
# Prerequisites:
#   - The local stack is up: `make up`
#   - Docker is on PATH
#
# What it does:
#   1. Recreates a fresh `art_local_restore` database on the local postgres
#      service (DROP IF EXISTS / CREATE).
#   2. Runs pg_restore inside `postgres:16`, joined to the compose network,
#      reading the dump file via a read-only bind mount.
#
# What it does NOT do:
#   - Touch the running app's `art_manufacturing` database.
#   - Connect to anything outside the compose network.
#   - Honor PGHOST / PGUSER / PGPASSWORD env vars from the caller (any
#     non-local value aborts the script).
#
# See scripts/db/README.md for the full workflow.

set -euo pipefail
export MSYS_NO_PATHCONV=1

DUMP_PATH="${1:-}"
if [ -z "${DUMP_PATH}" ]; then
  echo "Usage: $0 <path-to-dump-file>" >&2
  exit 1
fi
if [ ! -f "${DUMP_PATH}" ]; then
  echo "ERROR: dump file not found: ${DUMP_PATH}" >&2
  exit 1
fi

# Hard-locked LOCAL connection values. These match the compose service name
# and the seed credentials in .env.example.
LOCAL_HOST="postgres"
LOCAL_PORT="5432"
LOCAL_USER="art_user"
LOCAL_PASSWORD="art_password"
LOCAL_DB="art_local_restore"

# Compose network is "<project>_default". Project name defaults to the repo
# directory in lowercase ("art-azure-terraform"); override via env var if
# your `docker-compose -p <name>` differs.
COMPOSE_PROJECT="${COMPOSE_PROJECT:-art-azure-terraform}"
COMPOSE_NETWORK="${COMPOSE_PROJECT}_default"

# Refuse if caller has tried to redirect us at a remote host via PGHOST.
if [ -n "${PGHOST:-}" ] && [ "${PGHOST}" != "${LOCAL_HOST}" ] && [ "${PGHOST}" != "localhost" ]; then
  echo "ERROR: PGHOST is set to '${PGHOST}', which is not local." >&2
  echo "       This script restores ONLY to the local docker-compose postgres." >&2
  echo "       unset PGHOST and re-run." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not on PATH." >&2
  exit 3
fi

if ! docker network inspect "${COMPOSE_NETWORK}" >/dev/null 2>&1; then
  echo "ERROR: docker network '${COMPOSE_NETWORK}' not found." >&2
  echo "       Start the local stack first: make up" >&2
  echo "       (Or set COMPOSE_PROJECT=<name> if your compose project name differs.)" >&2
  exit 4
fi

DUMP_ABS_DIR="$(cd "$(dirname "${DUMP_PATH}")" && pwd)"
DUMP_NAME="$(basename "${DUMP_PATH}")"

echo "== Restoring ${DUMP_NAME} =="
echo "Dump file        : ${DUMP_ABS_DIR}/${DUMP_NAME}"
echo "Target host      : ${LOCAL_HOST} (compose network: ${COMPOSE_NETWORK})"
echo "Target user      : ${LOCAL_USER}"
echo "Target database  : ${LOCAL_DB}"
echo

echo "-- Recreating ${LOCAL_DB} --"
docker run --rm \
  --network "${COMPOSE_NETWORK}" \
  -e PGPASSWORD="${LOCAL_PASSWORD}" \
  postgres:16 \
  psql \
    --host="${LOCAL_HOST}" --port="${LOCAL_PORT}" --username="${LOCAL_USER}" \
    --dbname=postgres \
    -c "DROP DATABASE IF EXISTS ${LOCAL_DB};" \
    -c "CREATE DATABASE ${LOCAL_DB};"

echo
echo "-- pg_restore --"
docker run --rm \
  --network "${COMPOSE_NETWORK}" \
  -e PGPASSWORD="${LOCAL_PASSWORD}" \
  -v "${DUMP_ABS_DIR}:/in:ro" \
  postgres:16 \
  pg_restore \
    --verbose --clean --if-exists --no-owner --no-acl \
    --host="${LOCAL_HOST}" --port="${LOCAL_PORT}" --username="${LOCAL_USER}" \
    --dbname="${LOCAL_DB}" \
    "/in/${DUMP_NAME}"

echo
echo "== Done =="
echo "Restored ${DUMP_NAME} into local DB '${LOCAL_DB}'."
echo "Connect from host: psql -h localhost -p 5432 -U art_user -d ${LOCAL_DB}  (password: art_password)"
