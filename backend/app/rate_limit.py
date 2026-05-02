"""Rate limiting setup. In-process counters via slowapi.

The Web App runs uvicorn with --workers 2, so counters are per-worker — actual
limits are roughly 2x what you write here. Acceptable for our F1 deployment;
the goal is to stop credential-stuffing loops and protect the 60 CPU min/day
quota, not to enforce a precise SLA. Future upgrade: switch storage_uri to
the existing redis sidecar for shared counters.

Disabled when settings.app_env != "production" so docker-compose dev and
pytest are unaffected.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.config import settings


def _client_ip(request: Request) -> str:
    """Honor X-Forwarded-For so we rate-limit by the real client IP rather
    than the App Service load balancer's egress IP (which would lump every
    user under one bucket).

    Azure App Service prepends the source port to each XFF entry, e.g.
    `203.0.113.5:64923, 168.63.x.x:80`. Each TCP connection from the same
    client opens with a different ephemeral port, so without stripping the
    port slowapi sees every request as a brand-new user and the limit never
    triggers. Strip the port for IPv4 entries; leave IPv6 alone (Azure
    doesn't currently use IPv6 in XFF on Linux App Service).
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            # IPv6 literals in XFF are bracketed: [::1]:1234. IPv4 entries
            # like "1.2.3.4:5678" have a single colon — strip it.
            if first.startswith("["):
                # [v6]:port → keep [v6]
                return first.split("]")[0] + "]" if "]" in first else first
            if first.count(":") == 1:
                return first.rsplit(":", 1)[0]
            return first
    return get_remote_address(request)


# `enabled` toggles all decorated endpoints off in non-production environments
# (pytest, docker-compose dev). The decorators stay in place — slowapi just
# skips them.
#
# headers_enabled=False because slowapi 0.1.9 calls `_inject_headers` on the
# route's return value AFTER the handler runs — when the handler returns a
# plain dict (FastAPI's default for JSON responses) the inject step raises
# `Exception: parameter response must be an instance of starlette.responses.
# Response` and short-circuits the response. Disabling header injection keeps
# the rate-limit check itself in force; clients lose the X-RateLimit-* hints
# but still receive 429 once the bucket is exhausted.
limiter = Limiter(
    key_func=_client_ip,
    enabled=(settings.app_env == "production"),
    headers_enabled=False,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return our standard {detail, code} envelope so the frontend can show a
    consistent error toast."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "code": "rate_limit_exceeded",
        },
    )
