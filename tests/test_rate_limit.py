"""Tests for the in-memory rate limiter."""

from app.middleware.rate_limit import InMemoryRateLimiter, RateLimitConfig


class TestRateLimiter:
    """Test suite for the InMemoryRateLimiter."""

    def test_allows_requests_within_limit(self) -> None:
        """Requests within the limit should be allowed."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.check("test-key", config) is True

    def test_blocks_requests_exceeding_limit(self) -> None:
        """Requests exceeding the limit should be blocked."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.check("test-key", config) is True
        # Fourth request should be blocked
        assert limiter.check("test-key", config) is False

    def test_remaining_counts(self) -> None:
        """get_remaining should return correct count."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=10, window_seconds=60)
        assert limiter.get_remaining("test-key", config) == 10
        limiter.check("test-key", config)
        assert limiter.get_remaining("test-key", config) == 9

    def test_different_keys_independent(self) -> None:
        """Different keys should have independent counters."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=2, window_seconds=60)
        limiter.check("key-a", config)
        limiter.check("key-a", config)
        # key-a should be blocked now
        assert limiter.check("key-a", config) is False
        # key-b should still have 2 requests available
        assert limiter.check("key-b", config) is True
        assert limiter.check("key-b", config) is True

    def test_zero_max_requests_blocks_all(self) -> None:
        """Zero max requests should block everything."""
        limiter = InMemoryRateLimiter()
        config = RateLimitConfig(max_requests=0, window_seconds=60)
        assert limiter.check("test-key", config) is False
