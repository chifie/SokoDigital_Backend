"""Rate limiter for FastAPI — supports both in-memory and Redis backends.

- ``InMemoryRateLimiter`` — Simple sliding-window, suitable for single-instance deployments.
- ``RedisRateLimiter`` — Distributed rate limiting via Redis, suitable for multi-instance deployments.
- ``rate_limit()`` dependency — Auto-selects the best backend based on configuration.
"""

import logging
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Configuration for rate limiting.

    Attributes
    ----------
    max_requests : int
        Maximum number of requests allowed within the window.
    window_seconds : int
        Time window in seconds.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds


# Default rate limits per endpoint category
AUTH_RATE_LIMIT = RateLimitConfig(max_requests=10, window_seconds=60)  # 10 req/min
UPLOAD_RATE_LIMIT = RateLimitConfig(max_requests=20, window_seconds=60)  # 20 req/min
GENERAL_RATE_LIMIT = RateLimitConfig(max_requests=100, window_seconds=60)  # 100 req/min


class InMemoryRateLimiter:
    """Sliding-window rate limiter using an in-memory store (single-instance)."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, config: RateLimitConfig) -> bool:
        """Check if a request is allowed. Returns True if allowed."""
        now = time.time()
        window_start = now - config.window_seconds

        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        if len(self._requests[key]) >= config.max_requests:
            return False

        self._requests[key].append(now)
        return True

    def get_remaining(self, key: str, config: RateLimitConfig) -> int:
        """Get the number of remaining requests in the current window."""
        now = time.time()
        window_start = now - config.window_seconds

        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        return max(0, config.max_requests - len(self._requests[key]))

    async def close(self) -> None:
        """No-op for in-memory limiter."""
        pass


class RedisRateLimiter:
    """Sliding-window rate limiter backed by Redis (distributed).

    Uses a sorted set per key with timestamps as scores, and expires keys
    automatically via Redis TTL.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """Lazy-init the Redis client."""
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def check(self, key: str, config: RateLimitConfig) -> bool:
        """Check if a request is allowed. Returns True if allowed."""
        r = await self._get_redis()
        now = time.time()
        window_start = now - config.window_seconds
        window_key = f"ratelimit:{key}:{config.window_seconds}"

        async with r.pipeline(transaction=True) as pipe:
            # Remove old entries
            await pipe.zremrangebyscore(window_key, 0, window_start)
            # Count remaining entries
            await pipe.zcard(window_key)
            # Get TTL for expiry calculation
            await pipe.ttl(window_key)
            results = await pipe.execute()

        count = results[1]
        ttl = results[2]

        if count >= config.max_requests:
            return False

        # Add current request and set expiry
        async with r.pipeline(transaction=True) as pipe:
            await pipe.zadd(window_key, {str(now): now})
            if ttl < 0:
                await pipe.expire(window_key, config.window_seconds * 2)
            await pipe.execute()

        return True

    async def get_remaining(self, key: str, config: RateLimitConfig) -> int:
        """Get the number of remaining requests in the current window."""
        try:
            r = await self._get_redis()
            now = time.time()
            window_start = now - config.window_seconds
            window_key = f"ratelimit:{key}:{config.window_seconds}"

            await r.zremrangebyscore(window_key, 0, window_start)
            count = await r.zcard(window_key)
            return max(0, config.max_requests - count)
        except Exception:
            return config.max_requests

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None


# ── Auto-select backend ──────────────────────────────────────────────────────

_limiter: InMemoryRateLimiter | RedisRateLimiter

if settings.REDIS_URL:
    logger.info("Rate limiter: using Redis backend (%s)", settings.REDIS_URL)
    _limiter = RedisRateLimiter(settings.REDIS_URL)
else:
    logger.info("Rate limiter: using in-memory backend")
    _limiter = InMemoryRateLimiter()


def _get_client_key(request: Request) -> str:
    """Extract a unique client identifier from the request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    return client_ip


def rate_limit(config: RateLimitConfig = GENERAL_RATE_LIMIT) -> Callable:
    """FastAPI dependency that enforces rate limiting.

    Auto-selects the backend (in-memory or Redis) based on ``settings.REDIS_URL``.

    Usage:
    ```python
    from app.middleware.rate_limit import rate_limit, AUTH_RATE_LIMIT

    @router.post("/login")
    async def login(_, _rl=Depends(rate_limit(AUTH_RATE_LIMIT))):
        ...
    ```
    """

    async def dependency(request: Request) -> None:
        key = _get_client_key(request)
        allowed = await _limiter.check(key, config)
        if not allowed:
            remaining = await _limiter.get_remaining(key, config)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={
                    "Retry-After": str(config.window_seconds),
                    "X-RateLimit-Limit": str(config.max_requests),
                    "X-RateLimit-Remaining": str(remaining),
                },
            )

    return dependency

