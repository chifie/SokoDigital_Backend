"""Simple in-memory rate limiter for FastAPI.

Uses a sliding window approach. This is suitable for single-instance
deployments. For distributed deployments, replace with Redis-based
rate limiting (e.g., using slowapi or a custom Redis-backed limiter).
"""

import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


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
    """Sliding-window rate limiter using an in-memory store."""

    def __init__(self) -> None:
        # {key: [(timestamp, ...)]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, config: RateLimitConfig) -> bool:
        """Check if a request is allowed. Returns True if allowed."""
        now = time.time()
        window_start = now - config.window_seconds

        # Prune old entries
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

        # Prune old entries
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        return max(0, config.max_requests - len(self._requests[key]))


# Global rate limiter instance
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
        if not _limiter.check(key, config):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={
                    "Retry-After": str(config.window_seconds),
                    "X-RateLimit-Limit": str(config.max_requests),
                    "X-RateLimit-Remaining": str(
                        _limiter.get_remaining(key, config)
                    ),
                },
            )

    return dependency



