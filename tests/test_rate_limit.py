"""Tests for the in-memory rate limiter."""

import pytest

from app.middleware.rate_limit import InMemoryRateLimiter, RateLimitConfig


class TestRateLimiter:
    """Test suite for the InMemoryRateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self) -> None:
        """Requests within the limit should be allowed."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert await limiter.check("test-key", config) is True

    @pytest.mark.asyncio
    async def test_blocks_requests_exceeding_limit(self) -> None:
        """Requests exceeding the limit should be blocked."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert await limiter.check("test-key", config) is True
        # Fourth request should be blocked
        assert await limiter.check("test-key", config) is False

    @pytest.mark.asyncio
    async def test_remaining_counts(self) -> None:
        """get_remaining should return correct count."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=10, window_seconds=60)
        assert await limiter.get_remaining("test-key", config) == 10
        await limiter.check("test-key", config)
        assert await limiter.get_remaining("test-key", config) == 9

    @pytest.mark.asyncio
    async def test_different_keys_independent(self) -> None:
        """Different keys should have independent counters."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=2, window_seconds=60)
        await limiter.check("key-a", config)
        await limiter.check("key-a", config)
        # key-a should be blocked now
        assert await limiter.check("key-a", config) is False
        # key-b should still have 2 requests available
        assert await limiter.check("key-b", config) is True
        assert await limiter.check("key-b", config) is True

    @pytest.mark.asyncio
    async def test_zero_max_requests_blocks_all(self) -> None:
        """Zero max requests should block everything."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=0, window_seconds=60)
        assert await limiter.check("test-key", config) is False
