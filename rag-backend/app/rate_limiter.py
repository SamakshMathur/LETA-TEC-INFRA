"""
Shared rate-limiter instance.

Extracted from app.py so FastAPI routers (payments, admin, etc.) can import
the same Limiter without creating a circular import through app.py.

Usage in a router module:
    from app.rate_limiter import limiter
    from fastapi import Request

    @router.post("/some-endpoint")
    @limiter.limit("10/minute")
    def my_endpoint(request: Request, ...):
        ...

The `request: Request` parameter is required by slowapi — it must appear
in the function signature for the decorator to find it.
"""
import os
import base64 as _b64
import json as _json
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _rate_limit_key(request) -> str:
    """Prefer JWT user-ID over IP so limits survive proxy/CDN hops."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            parts = auth.split(".")
            if len(parts) == 3:
                padded = parts[1] + "=" * (-len(parts[1]) % 4)
                payload = _json.loads(_b64.b64decode(padded))
                if "sub" in payload:
                    return f"user:{payload['sub']}"
        except Exception:
            pass
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis as _r
        _r.from_url(_redis_url, socket_connect_timeout=1).ping()
        lim = Limiter(key_func=_rate_limit_key, storage_uri=_redis_url)
        logger.info("Rate limiter: Redis-backed (distributed)")
        return lim
    except Exception as _e:
        logger.warning(f"Rate limiter: in-memory fallback (Redis unavailable: {_e})")
        return Limiter(key_func=_rate_limit_key)


# Module-level singleton — imported by app.py (attached to app.state.limiter)
# and by any router that needs per-endpoint rate limits.
limiter = _build_limiter()
