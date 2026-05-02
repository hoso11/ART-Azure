"""Strict Origin / Referer check for unsafe HTTP methods.

CSRF defense layered on top of SameSite=Lax cookies. SameSite=Lax already
blocks most cross-site cookie attacks on POST/PUT/PATCH/DELETE, but a stricter
server-side check is cheap insurance:

  - On unsafe methods (POST, PUT, PATCH, DELETE):
      * Reject if neither Origin nor Referer is present.
      * Otherwise the source origin (parsed scheme://host[:port]) must be in
        settings.allowed_origins_list.
  - GET / HEAD / OPTIONS are never gated.

Disabled when settings.app_env != "production" so docker-compose dev and
pytest are unaffected. Server-to-server calls from the Next.js SSR layer
hit different routes (mostly GET) and run from inside the same Web App, so
they aren't impacted in practice.
"""

from urllib.parse import urlparse

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings


UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _origin_from_referer(referer: str | None) -> str | None:
    if not referer:
        return None
    try:
        parsed = urlparse(referer)
    except (ValueError, AttributeError):
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


class OriginCheckMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, allowed_origins: list[str], enabled: bool):
        super().__init__(app)
        self.allowed = {o.strip().rstrip("/") for o in allowed_origins if o.strip()}
        self.enabled = enabled

    async def dispatch(self, request, call_next):
        if not self.enabled:
            return await call_next(request)
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        origin = (request.headers.get("origin") or "").strip().rstrip("/") or None
        source = origin or _origin_from_referer(request.headers.get("referer"))

        if not source or source not in self.allowed:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Origin not allowed for this request.",
                    "code": "origin_forbidden",
                },
            )
        return await call_next(request)


def build_origin_middleware_args() -> dict:
    """Factory for FastAPI's add_middleware kwargs. Production-only; everything
    else (development, tests, staging) is a no-op pass-through."""
    return {
        "allowed_origins": settings.allowed_origins_list,
        "enabled": settings.app_env == "production",
    }
