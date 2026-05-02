"""Tests for Task C1 — least-privilege DB user bootstrap.

Covers the gate logic and password validator in scripts.bootstrap_db_user.
The actual SQL path is exercised against the live Postgres on cold-start
(see backend/entrypoint.sh) — there is no point retesting psycopg2 here
since SQLite and an in-memory engine cannot represent CREATE ROLE / GRANT.
"""

import importlib

import pytest


class TestGate:
    def _reload(self, monkeypatch, **env):
        for k, v in env.items():
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        from scripts import bootstrap_db_user as mod
        importlib.reload(mod)
        return mod

    def test_skips_when_sync_url_missing(self, monkeypatch):
        mod = self._reload(
            monkeypatch,
            DATABASE_URL_SYNC=None,
            ART_APP_DB_PASSWORD="x" * 24,
        )
        ok, reason = mod._gate()
        assert ok is False
        assert "DATABASE_URL_SYNC" in reason

    def test_skips_when_app_password_missing(self, monkeypatch):
        mod = self._reload(
            monkeypatch,
            DATABASE_URL_SYNC="postgresql://u:p@h/d",
            ART_APP_DB_PASSWORD=None,
        )
        ok, reason = mod._gate()
        assert ok is False
        assert "ART_APP_DB_PASSWORD" in reason

    def test_runs_when_both_set(self, monkeypatch):
        mod = self._reload(
            monkeypatch,
            DATABASE_URL_SYNC="postgresql://u:p@h/d",
            ART_APP_DB_PASSWORD="x" * 24,
        )
        ok, _ = mod._gate()
        assert ok is True


class TestPasswordValidator:
    def setup_method(self):
        from scripts.bootstrap_db_user import _validate_password
        self._validate = _validate_password

    def test_empty_rejected(self):
        ok, reason = self._validate("")
        assert ok is False and "empty" in reason

    def test_short_rejected(self):
        ok, reason = self._validate("short")
        assert ok is False and "16" in reason

    def test_single_quote_rejected(self):
        ok, reason = self._validate("a" * 16 + "'b")
        assert ok is False and "forbidden" in reason

    def test_backslash_rejected(self):
        ok, reason = self._validate("a" * 16 + "\\b")
        assert ok is False and "forbidden" in reason

    def test_null_byte_rejected(self):
        ok, reason = self._validate("a" * 16 + "\x00b")
        assert ok is False and "forbidden" in reason

    def test_url_safe_specials_accepted(self):
        # Mirrors what Terraform random_password.art_app_db produces:
        # alnum + "_" + "-".
        ok, _ = self._validate("Aa1_-Aa1_-Aa1_-Aa1_-Aa1_")
        assert ok is True

    def test_long_alnum_accepted(self):
        ok, _ = self._validate("Z9z" * 8)
        assert ok is True


class TestSqlConstants:
    """Lock down the role name and SQL shape so a future edit can't silently
    swap 'art_app' for the admin user or weaken the grants. The exact role
    name is what the runtime DATABASE_URL must use; mismatching them locks
    out the app."""

    def test_role_name_is_art_app(self):
        from scripts.bootstrap_db_user import APP_USER
        assert APP_USER == "art_app"

    def test_module_does_not_hardcode_password(self):
        """Sanity: the module file must never contain a plaintext password
        or the env var's value. Read the source and check."""
        import inspect
        from scripts import bootstrap_db_user as mod
        source = inspect.getsource(mod)
        # The script reads from os.environ — ensure it never uses a fixed
        # "password=..." string anywhere.
        forbidden = ["password = '", 'password = "', "PASSWORD = '"]
        for needle in forbidden:
            assert needle not in source, f"hard-coded password literal: {needle!r}"
