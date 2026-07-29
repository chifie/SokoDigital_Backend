"""Redis-backed response caching for frequently accessed endpoints.

Provides a FastAPI dependency and middleware that caches GET responses.
Cache keys are derived from the request method + path + query string.
Cache entries have a configurable TTL (default 60 seconds).

The cache is **lazy-initialized** — if Redis is not configured, the cache
falls back to a no-op pass-through so the application still works.

Usage — apply to specific routes as a dependency::

    from app.middleware.cache import cache

    @router.get(\"/categories\", dependencies=[Depends(cache(ttl=120))])
    async def list_categories(...):
        ...

Or use as a middleware to cache all GET responses automatically::

    from app.middleware.cache import CacheMiddleware
    app.add_middleware(CacheMiddleware, default_ttl=60)
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger(__name__)


# ── Redis client (lazy) ──────────────────────────────────────────────────────


_redis: Any = None


async def _get_redis() -> Any:
    """Lazy-init the Redis client for caching."""
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


# ── Cache dependency ─────────────────────────────────────────────────────────


def cache(
    ttl: int = 60,
    key_prefix: str = "cache",
) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """FastAPI dependency that caches GET responses.

    Parameters
    ----------
    ttl : int
        Time-to-live in seconds for the cache entry.
    key_prefix : str
        Prefix for the Redis key to avoid collisions.

    Usage::

        from app.middleware.cache import cache

        @router.get(\"/categories\", dependencies=[Depends(cache(ttl=120))])
        async def list_categories(...):
            ...
    """

    async def dependency(request: Request) -> None:
        # Cache only GET requests
        if request.method != "GET":
            return

        r = await _get_redis()
        if r is None:
            return  # No Redis — pass through

        key = _build_cache_key(request, prefix=key_prefix)
        cached = await r.get(key)

        if cached is not None:
            from fastapi.responses import JSONResponse

            data = json.loads(cached)
            # Store the cached response in request state so the middleware can use it
            request.state.cached_response = JSONResponse(
                content=data,
                headers={"X-Cache": "HIT"},
            )
            request.state.is_cached = True
        else:
            request.state.is_cached = False
            request.state.cache_key = key
            request.state.cache_ttl = ttl

    return dependency


# ── Middleware ───────────────────────────────────────────────────────────────


class CacheMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that caches GET responses in Redis.

    This is a **fallback** caching layer — it only caches responses whose
    routes do **not** already have the ``cache`` dependency applied
    (it checks ``request.state.is_cached``).

    To apply caching to a specific route, prefer the ``cache()``
    dependency instead, which is more granular.
    """

    def __init__(self, app: ASGIApp, default_ttl: int = 60) -> None:
        super().__init__(app)
        self.default_ttl = default_ttl

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # If the route already handled caching via the dependency, serve it
        if getattr(request.state, "is_cached", False) and hasattr(
            request.state, "cached_response"
        ):
            return request.state.cached_response  # type: ignore[return-value]

        response: Response = await call_next(request)

        # Cache successful GET responses if the route requested caching
        if (
            request.method == "GET"
            and response.status_code == 200
            and getattr(request.state, "is_cached", False) is False
            and getattr(request.state, "cache_key", None) is not None
        ):
            r = await _get_redis()
            if r is not None:
                try:
                    # Read the response body
                    body = b""
                    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                        body += chunk

                    # Store in cache
                    await r.setex(
                        request.state.cache_key,
                        getattr(request.state, "cache_ttl", self.default_ttl),
                        body.decode(),
                    )

                    # Rebuild response with cache header
                    response = Response(
                        content=body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                    response.headers["X-Cache"] = "MISS"

                    # Restore the body iterator for subsequent middleware
                    async def _body_iterator() -> Any:
                        yield body

                    response.body_iterator = _body_iterator()  # type: ignore[attr-defined]

                except Exception as exc:
                    logger.warning("Cache: failed to store response (%s)", exc)
        elif (
            request.method == "GET"
            and response.status_code == 200
            and getattr(request.state, "is_cached", False)
        ):
            # Cache HIT — add header
            response.headers["X-Cache"] = "HIT"

        return response
