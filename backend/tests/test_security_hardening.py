"""Tests for Task A — Critical credentials hardening.

Covers:
1. SECRET_KEY validator rejects known placeholders / short values when
   APP_ENV=production, but stays permissive in dev so docker-compose works.
2. _docs_kwargs disables Swagger / OpenAPI / ReDoc when APP_ENV=production.
3. seed._should_run_seed enforces ENABLE_SEED_DATA + ADMIN_INITIAL_PASSWORD
   in production and never lets the public default leak in.
"""

import importlib

import pytest
from pydantic import ValidationError

from app.config import Settings, WEAK_SECRET_KEYS
from app.main import _docs_kwargs


# ── SECRET_KEY validator ──────────────────────────────────────────────────

class TestSecretKey:
    def test_placeholder_rejected_in_production(self):
        with pytest.raises(ValidationError):
            Settings(
                app_env="production",
                secret_key="placeholder-dev-secret-change-me",
            )

    def test_change_me_rejected_in_production(self):
        with pytest.raises(ValidationError):
            Settings(app_env="production", secret_key="change-me")

    def test_empty_rejected_in_production(self):
        with pytest.raises(ValidationError):
            Settings(app_env="production", secret_key="")

    def test_short_rejected_in_production(self):
        with pytest.raises(ValidationError):
            Settings(app_env="production", secret_key="short-but-real")

    def test_strong_accepted_in_production(self):
        strong = "a" * 32
        s = Settings(app_env="production", secret_key=strong)
        assert s.secret_key == strong

    def test_placeholder_allowed_in_development(self):
        s = Settings(app_env="development", secret_key="change-me")
        assert s.secret_key == "change-me"

    def test_short_allowed_in_development(self):
        s = Settings(app_env="development", secret_key="x")
        assert s.secret_key == "x"

    def test_weak_set_covers_known_placeholders(self):
        assert "change-me" in WEAK_SECRET_KEYS
        assert "placeholder-dev-secret-change-me" in WEAK_SECRET_KEYS
        assert "" in WEAK_SECRET_KEYS


# ── FastAPI docs gating ───────────────────────────────────────────────────

class TestDocsKwargs:
    def test_production_disables_all_docs(self):
        kw = _docs_kwargs("production")
        assert kw["docs_url"] is None
        assert kw["openapi_url"] is None
        assert kw["redoc_url"] is None

    def test_development_enables_all_docs(self):
        kw = _docs_kwargs("development")
        assert kw["docs_url"] == "/api/v1/docs"
        assert kw["openapi_url"] == "/api/v1/openapi.json"
        assert kw["redoc_url"] == "/api/v1/redoc"

    def test_unknown_env_treated_as_dev(self):
        # Anything that is not the literal string "production" keeps docs on.
        # Conservative — avoids accidentally hiding docs in test/staging.
        for env in ("test", "staging", "local", ""):
            kw = _docs_kwargs(env)
            assert kw["docs_url"] is not None, f"expected docs in {env!r}"


# ── Seed gate ─────────────────────────────────────────────────────────────

class TestSeedGate:
    def _reload_seed(self, monkeypatch, **env: str):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        # Force settings + seed module to re-read environment.
        from app import config as app_config
        importlib.reload(app_config)
        from scripts import seed as seed_mod
        importlib.reload(seed_mod)
        return seed_mod

    def test_dev_default_runs_seed(self, monkeypatch):
        seed_mod = self._reload_seed(monkeypatch, APP_ENV="development")
        should, reason = seed_mod._should_run_seed()
        assert should is True
        assert "non-production" in reason

    def test_production_default_skips_seed(self, monkeypatch):
        monkeypatch.delenv("ENABLE_SEED_DATA", raising=False)
        monkeypatch.delenv("ADMIN_INITIAL_PASSWORD", raising=False)
        seed_mod = self._reload_seed(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="x" * 32,
        )
        should, reason = seed_mod._should_run_seed()
        assert should is False
        assert "ENABLE_SEED_DATA" in reason

    def test_production_without_admin_password_skips(self, monkeypatch):
        monkeypatch.delenv("ADMIN_INITIAL_PASSWORD", raising=False)
        seed_mod = self._reload_seed(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="x" * 32,
            ENABLE_SEED_DATA="true",
        )
        should, reason = seed_mod._should_run_seed()
        assert should is False
        assert "ADMIN_INITIAL_PASSWORD" in reason

    def test_production_with_default_admin_password_skips(self, monkeypatch):
        seed_mod = self._reload_seed(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="x" * 32,
            ENABLE_SEED_DATA="true",
            ADMIN_INITIAL_PASSWORD="admin123456",
        )
        should, reason = seed_mod._should_run_seed()
        assert should is False
        assert "weak" in reason.lower() or "default" in reason.lower()

    def test_production_with_short_admin_password_skips(self, monkeypatch):
        seed_mod = self._reload_seed(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="x" * 32,
            ENABLE_SEED_DATA="true",
            ADMIN_INITIAL_PASSWORD="short",
        )
        should, reason = seed_mod._should_run_seed()
        assert should is False

    def test_production_with_strong_admin_password_runs(self, monkeypatch):
        seed_mod = self._reload_seed(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="x" * 32,
            ENABLE_SEED_DATA="true",
            ADMIN_INITIAL_PASSWORD="A-Strong-Random-Passphrase-2026",
        )
        should, reason = seed_mod._should_run_seed()
        assert should is True

    def test_weak_password_set_includes_repo_default(self):
        from scripts.seed import WEAK_ADMIN_PASSWORDS, DEFAULT_ADMIN_PASSWORD
        assert DEFAULT_ADMIN_PASSWORD in WEAK_ADMIN_PASSWORDS
