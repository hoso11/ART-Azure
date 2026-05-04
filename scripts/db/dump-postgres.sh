#!/usr/bin/env bash
# Dump an Azure PostgreSQL Flexible Server database to a local custom-format
# file. Defaults to the dev environment; production requires
# ART_DUMP_ALLOW_PROD=1 AND explicit per-run approval.
#
# Usage (from repo root):
#   source terraform/envs/dev/.env.terraform
#   export PGHOST="$(terraform -chdir=terraform/envs/dev output -raw postgres_fqdn)"
#   export PGDATABASE="$(terraform -chdir=terraform/envs/dev output -raw postgres_database)"
#   export PGUSER="$(terraform -chdir=terraform/envs/dev output -raw postgres_admin_user)"
#   export PGPASSWORD="$(terraform -chdir=terraform/envs/dev output -raw postgres_admin_password)"
#   ./scripts/db/dump-postgres.sh
#
# Output:
#   backups/postgres/art-<env>-postgres-YYYY-MM-DD-HHMMSS.dump
#
# Safety:
#   - Password is read from PGPASSWORD env var only — never on the command
#     line, never echoed, never written to disk.
#   - `set -x` is intentionally NOT used.
#   - PGPASSWORD is unset on exit via trap.
#   - pg_dump runs inside `postgres:16` so the client matches the server
#     version exactly without requiring a host install.
#
# See scripts/db/README.md for the full workflow, firewall notes, and
# restore instructions.

set -euo pipefail

# Defensive against Git Bash on Windows: prevents MSYS from rewriting the
# `/out` mount path forwarded to `docker run -v ...:/out`.
export MSYS_NO_PATHCONV=1

ART_DUMP_ENV="${ART_DUMP_ENV:-dev}"

# Production gate.
if [ "${ART_DUMP_ENV}" = "prod" ] && [ "${ART_DUMP_ALLOW_PROD:-0}" != "1" ]; then
  echo "ERROR: ART_DUMP_ENV=prod requires ART_DUMP_ALLOW_PROD=1." >&2
  echo "       Production dumps also require explicit per-run user approval." >&2
  exit 2
fi

# Required env vars (the :? form aborts with a clean message if unset/empty
# and never expands the value).
: "${PGHOST:?PGHOST not set — see scripts/db/README.md}"
: "${PGDATABASE:?PGDATABASE not set — see scripts/db/README.md}"
: "${PGUSER:?PGUSER not set — see scripts/db/README.md}"
: "${PGPASSWORD:?PGPASSWORD not set — see scripts/db/README.md}"

# Defaults
export PGPORT="${PGPORT:-5432}"
export PGSSLMODE="${PGSSLMODE:-require}"

# Clear PGPASSWORD on exit. This only affects this script's environment;
# the caller's shell still holds the value, but later error paths inside
# this process can't accidentally leak it.
cleanup() {
  unset PGPASSWORD || true
}
trap cleanup EXIT

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not on PATH. Install Docker Desktop and re-run." >&2
  exit 3
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUTDIR="${REPO_ROOT}/backups/postgres"
mkdir -p "${OUTDIR}"

TIMESTAMP="$(date -u +%Y-%m-%d-%H%M%S)"
OUTFILE="art-${ART_DUMP_ENV}-postgres-${TIMESTAMP}.dump"

echo "== PostgreSQL dump =="
echo "Environment : ${ART_DUMP_ENV}"
echo "Host        : ${PGHOST}"
echo "Port        : ${PGPORT}"
echo "Database    : ${PGDATABASE}"
echo "User        : ${PGUSER}"
echo "SSL mode    : ${PGSSLMODE}"
echo "Output      : ${OUTDIR}/${OUTFILE}"
echo

# pg_dump inside postgres:16. Password forwarded via env, never as an arg.
if ! docker run --rm \
      -e PGHOST -e PGPORT -e PGDATABASE -e PGUSER -e PGPASSWORD -e PGSSLMODE \
      -v "${OUTDIR}:/out" \
      postgres:16 \
      pg_dump \
        --format=custom --verbose --no-owner --no-acl \
        --exclude-schema=cron --exclude-schema=pgaadauth \
        --file="/out/${OUTFILE}"; then
  echo >&2
  echo "ERROR: pg_dump failed." >&2
  echo "Likely cause: Azure PostgreSQL firewall does not allow this client IP." >&2
  echo "See scripts/db/README.md (Firewall) for the safe workflow to add a" >&2
  echo "temporary rule for your current public IP." >&2
  exit 4
fi

SIZE="$(du -h "${OUTDIR}/${OUTFILE}" | awk '{print $1}')"
echo
echo "== Done =="
echo "Wrote ${OUTDIR}/${OUTFILE} (${SIZE})"
