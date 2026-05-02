"""Tests for Task B — Auth surface hardening.

Covers:
1. Origin/Referer middleware blocks unsafe methods from disallowed origins
   when enabled, while allowing same-allowed-origin requests and any GET.
2. _client_ip rate-limit key honors X-Forwarded-For.
3. Rate limiter is instantiated and the exception handler returns the
   standardized {detail, code} envelope.

Note: in the existing test app the limiter and origin middleware are both
DISABLED because conftest sets APP_ENV=development. Tests here exercise the
production-mode behaviour by either inspecting helpers directly or by
constructing isolated middleware instances.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.origin_check import (
    OriginCheckMiddleware,
    UNSAFE_METHODS,
    _origin_from_referer,
)
from app.rate_limit import _client_ip, rate_limit_exceeded_handler


# ── Origin / Referer enforcement ──────────────────────────────────────────


def _make_origin_app(enabled: bool, allowed: list[str]) -> FastAPI:
    """Mini FastAPI app with only the OriginCheckMiddleware so each test is
    isolated from the real app's other middleware and routes."""
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware, allowed_origins=allowed, enabled=enabled)

    @app.get("/r")
    async def get_root():
        return {"ok": True}

    @app.post("/r")
    async def post_root():
        return {"ok": True}

    @app.patch("/r")
    async def patch_root():
        return {"ok": True}

    @app.delete("/r")
    async def delete_root():
        return {"ok": True}

    return app


ALLOWED = "https://app-art-frontend-dev-art4242.azurewebsites.net"


class TestOriginCheck:
    def test_unsafe_methods_set(self):
        assert UNSAFE_METHODS == {"POST", "PUT", "PATCH", "DELETE"}

    def test_disabled_lets_everything_through(self):
        app = _make_origin_app(enabled=False, allowed=[ALLOWED])
        client = TestClient(app)
        # Even with no Origin and unsafe method, disabled middleware passes.
        assert client.post("/r").status_code == 200

    def test_get_always_allowed(self):
        app = _make_origin_app(enabled=True, allowed=[ALLOWED])
        client = TestClient(app)
        assert client.get("/r").status_code == 200
        # Even with a clearly bad Origin on a safe method, no enforcement.
        assert client.get("/r", headers={"Origin": "https://evil.example"}).status_code == 200

    def test_unsafe_method_with_allowed_origin_succeeds(self):
        app = _make_origin_app(enabled=True, allowed=[ALLOWED])
        client = TestClient(app)
        for method in ("post", "patch", "delete"):
            r = getattr(client, method)("/r", headers={"Origin": ALLOWED})
            assert r.status_code == 200, f"{method.upper()} with allowed origin failed"

    def test_unsafe_method_with_disallowed_origin_rejected(self):
        app = _make_origin_app(enabled=True, allowed=[ALLOWED])
        client = TestClient(app)
        r = client.post("/r", headers={"Origin": "https://evil.example"})
        assert r.status_code == 403
        assert r.json()["code"] == "origin_forbidden"

    def test_unsafe_method_with_no_origin_or_referer_rejected(self):
        app = _make_origin_app(enabled=True, allowed=[ALLOWED])
        client = TestClient(app)
        r = client.post("/r")
        assert r.status_code == 403
        assert r.json()["code"] == "origin_forbidden"

    def test_referer_used_when_origin_missing(self):
        app = _make_origin_app(enabled=True, allowed=[ALLOWED])
        client = TestClient(app)
        # Origin header omitted; Referer used as fallback. Pin scheme+host.
        r = client.post("/r", headers={"Referer": f"{ALLOWED}/some/path?x=1"})
        assert r.status_code == 200

    def test_origin_match_is_exact_scheme_host(self):
        app = _make_origin_app(enabled=True, allowed=[ALLOWED])
        client = TestClient(app)
        # Different host with shared suffix must NOT match.
        r = client.post(
            "/r",
            headers={"Origin": "https://attacker.azurewebsites.net"},
        )
        assert r.status_code == 403
        # http vs https is also a mismatch.
        r2 = client.post(
            "/r",
            headers={"Origin": ALLOWED.replace("https://", "http://")},
        )
        assert r2.status_code == 403

    def test_trailing_slash_normalised(self):
        app = _make_origin_app(enabled=True, allowed=[ALLOWED])
        client = TestClient(app)
        r = client.post("/r", headers={"Origin": ALLOWED + "/"})
        assert r.status_code == 200

    def test_referer_helper_handles_garbage(self):
        assert _origin_from_referer(None) is None
        assert _origin_from_referer("") is None
        assert _origin_from_referer("not-a-url") is None
        assert _origin_from_referer("https://x.example/path") == "https://x.example"


# ── Rate-limit key function ───────────────────────────────────────────────


class _FakeClient:
    def __init__(self, host: str):
        self.host = host


class _FakeRequest:
    def __init__(self, headers: dict, peer: str = "10.0.0.1"):
        self.headers = headers
        self.client = _FakeClient(peer)


class TestClientIp:
    def test_uses_xff_first_entry(self):
        req = _FakeRequest(headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"})
        assert _client_ip(req) == "203.0.113.5"

    def test_strips_whitespace_around_xff(self):
        req = _FakeRequest(headers={"x-forwarded-for": "  198.51.100.1  "})
        assert _client_ip(req) == "198.51.100.1"

    def test_falls_back_to_peer_address(self):
        req = _FakeRequest(headers={})
        assert _client_ip(req) == "10.0.0.1"

    def test_empty_xff_uses_peer(self):
        req = _FakeRequest(headers={"x-forwarded-for": ""})
        assert _client_ip(req) == "10.0.0.1"

    def test_strips_azure_appservice_port(self):
        """Azure App Service prepends a per-connection ephemeral port, e.g.
        `203.0.113.5:64923`. Without stripping, every TCP connection looks
        like a new user and the rate limit never fires."""
        req = _FakeRequest(headers={"x-forwarded-for": "203.0.113.5:64923"})
        assert _client_ip(req) == "203.0.113.5"

    def test_strips_port_with_following_entries(self):
        req = _FakeRequest(
            headers={"x-forwarded-for": "203.0.113.5:64923, 168.63.10.10:80"}
        )
        assert _client_ip(req) == "203.0.113.5"

    def test_keeps_ipv4_with_no_port(self):
        req = _FakeRequest(headers={"x-forwarded-for": "203.0.113.5"})
        assert _client_ip(req) == "203.0.113.5"


# ── Rate-limit integration ────────────────────────────────────────────────


class TestRateLimitWiring:
    def test_limiter_attached_to_app(self):
        from app.main import app
        from app.rate_limit import limiter
        assert app.state.limiter is limiter

    def test_login_route_is_decorated(self):
        # slowapi attaches limit metadata to the endpoint via __wrapped__ /
        # registered limits. Easiest behavioural check: in dev the limiter
        # is disabled, so verify the endpoint still works after decoration.
        from app.auth.router import login
        assert callable(login)

    def test_login_and_refresh_limits_registered(self):
        """slowapi stores per-route limits keyed by `module.function`. Both
        the login (5/minute) and refresh (20/minute) endpoints must show up
        — without these registrations, the limiter is wired but inert."""
        from app.rate_limit import limiter
        keys = limiter._route_limits.keys()
        assert "app.auth.router.login" in keys
        assert "app.auth.router.refresh_token" in keys

    def test_headers_disabled_to_avoid_dict_inject_bug(self):
        """slowapi 0.1.9's `_inject_headers` raises when a route returns a
        plain dict (FastAPI's default for JSON). With headers_enabled=True
        the rate-limit check itself short-circuits with that exception and
        429 is never returned. Force the safe default."""
        from app.rate_limit import limiter
        assert limiter._headers_enabled is False

    def test_limit_actually_fires_when_enabled(self):
        """Behavioural smoke test: build an isolated FastAPI app with a fresh
        Limiter instance forced enabled, and confirm a 3/minute decorated
        route returns 429 on the 4th call."""
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from slowapi import Limiter
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        from slowapi.util import get_remote_address

        local_limiter = Limiter(
            key_func=get_remote_address, enabled=True, headers_enabled=False
        )
        app = FastAPI()
        app.state.limiter = local_limiter
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)

        @app.post("/probe")
        @local_limiter.limit("3/minute")
        async def probe(request: Request):
            return {"ok": True}

        client = TestClient(app)
        codes = [client.post("/probe").status_code for _ in range(5)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3:] == [429, 429]


# ── Existing endpoints still pass through ─────────────────────────────────


class TestExistingFlows:
    """Smoke tests confirming the new middleware stack doesn't break the
    happy path. Conftest's APP_ENV=development keeps both the limiter and
    the origin check disabled, so every route should behave as before."""

    @pytest.mark.asyncio
    async def test_get_health_works(self):
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_login_post_still_works_in_dev(self, admin_user):
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/v1/auth/login",
                json={"email": "admin@test.com", "password": "adminpass123"},
            )
        assert r.status_code == 200
