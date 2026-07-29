"""Redis-backed response caching middleware for frequently accessed GET endpoints.

The middleware checks Redis before forwarding the request. On a cache hit
the cached response is returned immediately, avoiding the route handler
entirely. On a cache miss the response is stored in Redis for subsequent
requests.

Cache keys are derived from ``request.method + request.url.path + request.url.query``
(SHA-256 hashed). The default TTL is configured via ``CACHE_DEFAULT_TTL``
setting (fallback: 60 s).

Usage in ``main.py``::

    from app.middleware.cache import CacheMiddleware

    app.add_middleware(CacheMiddleware, default_ttl=60)
"""

import hashlib
import json
import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger(__name__)


# ── Redis client (lazy) ──────────────────────────────────────────────────────

_redis: object | None = None  # Can be None, a Redis client, or False sentinel


async def _get_redis() -> object | None:
    """Lazy-init the Redis client for caching. Returns ``None`` if unavailable."""
    global _redis
    if _redis is None and settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis

            _redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Cache: Redis backend initialized (%s)", settings.REDIS_URL)
        except Exception as exc:
            logger.warning("Cache: failed to connect to Redis (%s)", exc)
            _redis = False  # Sentinel to avoid retrying
    elif _redis is None:
        _redis = False  # No Redis configured
    return _redis if _redis is not False else None


async def close_cache() -> None:
    """Close the Redis connection pool."""
    global _redis
    if _redis and _redis is not False:
        try:
            import redis.asyncio as aioredis

            if isinstance(_redis, aioredis.Redis):
                await _redis.close()
        except Exception:
            pass
        _redis = None


# ── Cache key helpers ────────────────────────────────────────────────────────


def _build_cache_key(request: Request, prefix: str = "cache") -> str:
    """Build a deterministic cache key from the request."""
    key_parts = [
        request.method,
        request.url.path,
        request.url.query,
    ]
    raw = ":".join(key_parts)
    hashed = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"{prefix}:{hashed}"


# ── Middleware ───────────────────────────────────────────────────────────────


class CacheMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that caches GET responses in Redis.

    On a cache hit the cached JSON response is returned immediately without
    forwarding the request to the route handler. On a miss the response is
    stored in Redis with the configured TTL.

    Only ``200 OK`` responses to ``GET`` requests are cached. Responses with
    ``Vary``, ``Set-Cookie``, or ``Authorization``-dependent headers are
    skipped to avoid serving stale or private data.
    """

    def __init__(self, app: ASGIApp, default_ttl: int = 60) -> None:
        super().__init__(app)
        self.default_ttl = default_ttl

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # ── Cache HIT: return cached response immediately ────────────────
        if request.method == "GET":
            cached = await self._try_serve_from_cache(request)
            if cached is not None:
                return cached

        # ── Cache MISS: forward request and optionally cache response ────
        response: Response = await call_next(request)

        if (
            request.method == "GET"
            and response.status_code == 200
            and _redis is not False  # Redis is available
            and self._should_cache(response)
        ):
            await self._try_store_in_cache(request, response)

        return response

    # ── Internal helpers ──────────────────────────────────────────────────

    async def _try_serve_from_cache(self, request: Request) -> Response | None:
        """Check Redis for a cached response. Returns a ``Response`` or ``None``."""
        r = await _get_redis()
        if r is None:
            return None

        key = _build_cache_key(request)
        try:
            import redis.asyncio as aioredis

            assert isinstance(r, aioredis.Redis)
            cached_data = await r.get(key)
        except Exception as exc:
            logger.warning("Cache: read error (%s)", exc)
            return None

        if cached_data is None:
            return None

        try:
            data = json.loads(cached_data)
        except (json.JSONDecodeError, TypeError):
            return None

        from starlette.responses import JSONResponse

        return JSONResponse(
            content=data,
            headers={
                "Content-Type": "application/json",
                "X-Cache": "HIT",
            },
        )

    async def _try_store_in_cache(
        self, request: Request, response: Response
    ) -> None:
        """Store the response body in Redis."""
        r = await _get_redis()
        if r is None:
            return

        key = _build_cache_key(request)
        body = response.body  # bytes — safe to read on Starlette responses

        try:
            import redis.asyncio as aioredis

            assert isinstance(r, aioredis.Redis)
            await r.setex(key, self.default_ttl, body)
        except Exception as exc:
            logger.warning("Cache: write error (%s)", exc)
            return

        # Add cache header to the original response (mutating is fine here)
        response.headers["X-Cache"] = "MISS"

    @staticmethod
    def _should_cache(response: Response) -> bool:
        """Return ``True`` if the response is safe to cache."""
        # Never cache responses with Set-Cookie or Vary headers
        if "set-cookie" in response.headers:
            return False
        # Only cache JSON responses
        content_type = response.media_type or ""
        return "json" in content_type
