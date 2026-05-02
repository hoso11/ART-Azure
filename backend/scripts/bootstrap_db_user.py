"""Bootstrap the least-privilege application DB user.

Runs every cold start from entrypoint.sh AFTER `alembic upgrade head` and
BEFORE uvicorn starts. Connects as the server admin via DATABASE_URL_SYNC
and idempotently:

  1. Creates role `art_app` (LOGIN) if missing.
  2. Sets / rotates its password from ART_APP_DB_PASSWORD.
  3. Grants CONNECT on the current database.
  4. Grants USAGE on schema public.
  5. Grants SELECT/INSERT/UPDATE/DELETE on all current tables.
  6. Grants USAGE/SELECT on all current sequences.
  7. ALTER DEFAULT PRIVILEGES so future tables and sequences also work.

The password value is NEVER hard-coded here and never logged. It comes
from the environment variable populated by the Terraform random_password
resource.

Skips silently when `ART_APP_DB_PASSWORD` is not set or when
`DATABASE_URL_SYNC` is missing — that's the docker-compose / pytest path
where the local backend is fine connecting as the dev admin user
(art_user). Production Web App always has both vars set.
"""

from __future__ import annotations

import os
import sys

import psycopg2
from psycopg2 import sql

APP_USER = "art_app"


def _gate() -> tuple[bool, str]:
    if not os.environ.get("DATABASE_URL_SYNC"):
        return False, "DATABASE_URL_SYNC not set"
    if not os.environ.get("ART_APP_DB_PASSWORD"):
        return False, "ART_APP_DB_PASSWORD not set"
    return True, "ok"


def _validate_password(pw: str) -> tuple[bool, str]:
    """Belt-and-braces — Terraform's `random_password.art_app_db` is
    constrained to URL-unreserved characters via `override_special = "_-"`,
    so quotes and backslashes are impossible. This guard just keeps a
    misuse from later (e.g. someone hand-overrides the env in a debug
    session) from injecting SQL via the password."""
    if not pw:
        return False, "empty"
    if len(pw) < 16:
        return False, "shorter than 16 chars"
    if "'" in pw or "\\" in pw or "\x00" in pw:
        return False, "contains forbidden character"
    return True, "ok"


def bootstrap() -> int:
    ok, reason = _gate()
    if not ok:
        print(f"[bootstrap_db_user] skipped: {reason}", flush=True)
        return 0

    sync_url = os.environ["DATABASE_URL_SYNC"]
    app_pw = os.environ["ART_APP_DB_PASSWORD"]

    pw_ok, pw_reason = _validate_password(app_pw)
    if not pw_ok:
        print(
            f"[bootstrap_db_user] FATAL: ART_APP_DB_PASSWORD invalid ({pw_reason})",
            file=sys.stderr,
            flush=True,
        )
        return 1

    try:
        conn = psycopg2.connect(sync_url)
    except psycopg2.OperationalError as exc:
        print(f"[bootstrap_db_user] FATAL: cannot connect: {exc}", file=sys.stderr, flush=True)
        return 1

    try:
        conn.autocommit = True
        cur = conn.cursor()

        # Discover current database name so the GRANT CONNECT call doesn't
        # need a separate config var.
        cur.execute("SELECT current_database();")
        (db_name,) = cur.fetchone()

        # 1. Create the role if missing. SECURITY: role name is a Python
        # constant — no user input flows into the DO block. Password is
        # NOT set here to avoid logging it via pg_stat_statements.
        cur.execute(
            f"""
            DO $bootstrap$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_USER}') THEN
                EXECUTE 'CREATE ROLE {APP_USER} LOGIN';
              END IF;
            END
            $bootstrap$;
            """
        )

        # 2. Set/rotate password. Use psycopg2.sql.Literal so the password
        # value is properly quoted — never string-formatted into raw SQL.
        cur.execute(
            sql.SQL("ALTER ROLE {role} WITH LOGIN PASSWORD {pw}").format(
                role=sql.Identifier(APP_USER),
                pw=sql.Literal(app_pw),
            )
        )

        # 3. CONNECT on current database
        cur.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {db} TO {role}").format(
                db=sql.Identifier(db_name),
                role=sql.Identifier(APP_USER),
            )
        )

        # 4. USAGE on schema public
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {role}").format(
                role=sql.Identifier(APP_USER),
            )
        )

        # 5. CRUD on existing tables
        cur.execute(
            sql.SQL(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"
            ).format(role=sql.Identifier(APP_USER))
        )

        # 6. USAGE/SELECT on existing sequences (needed for SERIAL ids)
        cur.execute(
            sql.SQL(
                "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"
            ).format(role=sql.Identifier(APP_USER))
        )

        # 7a. Default privileges so newly-created tables auto-grant.
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}"
            ).format(role=sql.Identifier(APP_USER))
        )

        # 7b. Default privileges for future sequences.
        cur.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                "GRANT USAGE, SELECT ON SEQUENCES TO {role}"
            ).format(role=sql.Identifier(APP_USER))
        )

        cur.close()
    finally:
        conn.close()

    # Never log the password. Just confirm structurally.
    print(
        f"[bootstrap_db_user] ok: role {APP_USER} configured against "
        f"database {db_name!r} (password rotated, grants reapplied)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(bootstrap())
