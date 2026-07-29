"""Unit tests for the ARQ background task handlers.

Tests cover:
- ``send_email_task`` — success and failure paths
- ``invalidate_cache_task`` — key prefix, pattern, no Redis, errors
- ``enqueue_email`` — fallback to synchronous send when ARQ/Redis unavailable
- ``enqueue_cache_invalidation`` — fallback to inline invalidation
- ``close_arq_pool`` — safe teardown

These tests avoid actually connecting to Redis or SMTP by mocking the
external dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import (
    close_arq_pool,
    enqueue_cache_invalidation,
    enqueue_email,
    invalidate_cache_task,
    send_email_task,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_arq_pool():
    """Reset the global ARQ pool before/after each test."""
    import app.tasks as tasks_module

    tasks_module._arq_pool = None
    yield
    tasks_module._arq_pool = None


@pytest.fixture
def mock_send_email():
    """Mock the underlying ``_send_email`` function."""
    with patch("app.tasks._send_email", new_callable=AsyncMock) as m:
        m.return_value = True
        yield m


# ── Tests for send_email_task ────────────────────────────────────────────────


class TestSendEmailTask:
    """Tests for the ``send_email_task`` ARQ handler."""

    @pytest.mark.asyncio
    async def test_sends_email_successfully(self, mock_send_email):
        result = await send_email_task(
            {},
            to_email="test@example.com",
            template_name="welcome",
            context={"name": "Alice"},
        )

        assert result is True
        mock_send_email.assert_awaited_once_with(
            "test@example.com", "welcome", {"name": "Alice"}
        )

    @pytest.mark.asyncio
    async def test_uses_empty_context_when_none(self, mock_send_email):
        result = await send_email_task(
            {},
            to_email="test@example.com",
            template_name="welcome",
        )

        assert result is True
        mock_send_email.assert_awaited_once_with(
            "test@example.com", "welcome", {}
        )

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self, mock_send_email):
        mock_send_email.side_effect = RuntimeError("SMTP down")

        result = await send_email_task(
            {},
            to_email="test@example.com",
            template_name="welcome",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_accepts_ctx_dict(self, mock_send_email):
        """The ARQ ``ctx`` is accepted but not required for this task."""
        ctx = {"job_id": "abc123", "redis": None}
        result = await send_email_task(
            ctx,
            to_email="test@example.com",
            template_name="welcome",
            context={"name": "Alice"},
        )

        assert result is True


# ── Tests for invalidate_cache_task ──────────────────────────────────────────


class TestInvalidateCacheTask:
    """Tests for the ``invalidate_cache_task`` ARQ handler."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_redis(self):
        """Without REDIS_URL, the task should short-circuit."""
        with patch("app.tasks.settings.REDIS_URL", None):
            result = await invalidate_cache_task({}, key_prefix="cache:")
            assert result == 0

    @pytest.mark.asyncio
    async def test_deletes_by_prefix(self):
        """Test that keys matching a prefix are deleted."""
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["cache:foo", "cache:bar"]
        mock_redis.delete.return_value = 2

        with (
            patch("app.tasks.settings.REDIS_URL", "redis://localhost:6379/0"),
            patch("redis.asyncio.from_url", return_value=mock_redis),
        ):
            result = await invalidate_cache_task({}, key_prefix="cache:")

        assert result == 2
        mock_redis.keys.assert_called_once_with("cache:*")
        mock_redis.delete.assert_called_once_with("cache:foo", "cache:bar")

    @pytest.mark.asyncio
    async def test_deletes_by_pattern(self):
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["prod:1", "prod:2"]
        mock_redis.delete.return_value = 2

        with (
            patch("app.tasks.settings.REDIS_URL", "redis://localhost:6379/0"),
            patch("redis.asyncio.from_url", return_value=mock_redis),
        ):
            result = await invalidate_cache_task({}, pattern="prod:*")

        assert result == 2
        mock_redis.keys.assert_called_once_with("prod:*")

    @pytest.mark.asyncio
    async def test_handles_no_matching_keys(self):
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = []

        with (
            patch("app.tasks.settings.REDIS_URL", "redis://localhost:6379/0"),
            patch("redis.asyncio.from_url", return_value=mock_redis),
        ):
            result = await invalidate_cache_task({}, key_prefix="nonexistent:")

        assert result == 0
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self):
        mock_redis = AsyncMock()
        mock_redis.keys.side_effect = ConnectionError("Redis unreachable")

        with (
            patch("app.tasks.settings.REDIS_URL", "redis://localhost:6379/0"),
            patch("redis.asyncio.from_url", return_value=mock_redis),
        ):
            result = await invalidate_cache_task({}, key_prefix="cache:")

        assert result == 0  # Graceful fallback


# ── Tests for enqueue helpers ────────────────────────────────────────────────


class TestEnqueueEmail:
    """Tests for the ``enqueue_email`` helper."""

    @pytest.mark.asyncio
    async def test_falls_back_to_sync_when_no_arq(self, mock_send_email):
        """When ARQ is imported but no pool exists (no Redis), fallback to sync."""
        with (
            patch("app.tasks._get_arq_pool", return_value=None),
        ):
            result = await enqueue_email(
                to_email="test@example.com",
                template_name="welcome",
                context={"name": "Alice"},
            )

        assert result is True
        mock_send_email.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enqueues_job_when_pool_available(self, mock_send_email):
        """When ARQ pool is available, a job should be enqueued."""
        mock_pool = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "job_123"
        mock_pool.enqueue_job.return_value = mock_job

        # Mock arq import so the function can find it
        with (
            patch.dict("sys.modules", {"arq": MagicMock()}),
            patch("app.tasks._get_arq_pool", return_value=mock_pool),
        ):
            # Re-import the module so it uses the mocked arq
            import importlib
            import app.tasks
            importlib.reload(app.tasks)

            result = await app.tasks.enqueue_email(
                to_email="test@example.com",
                template_name="welcome",
            )

        assert result is True
        mock_pool.enqueue_job.assert_awaited_once_with(
            "send_email_task",
            "test@example.com",
            "welcome",
            {},
        )
        # Should NOT fallback to sync send when enqueue succeeds
        mock_send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_on_enqueue_error(self, mock_send_email):
        """If enqueue_job raises, fallback to sync send."""
        mock_pool = AsyncMock()
        mock_pool.enqueue_job.side_effect = RuntimeError("Queue full")

        with patch("app.tasks._get_arq_pool", return_value=mock_pool):
            result = await enqueue_email(
                to_email="test@example.com",
                template_name="welcome",
            )

        assert result is True
        mock_send_email.assert_awaited_once()


class TestEnqueueCacheInvalidation:
    """Tests for the ``enqueue_cache_invalidation`` helper."""

    @pytest.mark.asyncio
    async def test_falls_back_to_inline_when_no_pool(self):
        """When no ARQ pool, run invalidation inline."""
        with (
            patch("app.tasks._get_arq_pool", return_value=None),
            patch("app.tasks.invalidate_cache_task", new_callable=AsyncMock, return_value=3) as mock_inline,
        ):
            result = await enqueue_cache_invalidation("cache:")

        assert result == 3
        mock_inline.assert_awaited_once_with({}, "cache:", None)

    @pytest.mark.asyncio
    async def test_enqueues_when_pool_available(self):
        mock_pool = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "inv_456"
        mock_pool.enqueue_job.return_value = mock_job

        with (
            patch.dict("sys.modules", {"arq": MagicMock()}),
            patch("app.tasks._get_arq_pool", return_value=mock_pool),
            patch("app.tasks.invalidate_cache_task", new_callable=AsyncMock) as mock_inline,
        ):
            import importlib
            import app.tasks
            importlib.reload(app.tasks)

            result = await app.tasks.enqueue_cache_invalidation(pattern="prod:*")

        assert result == 0  # Unknown until task runs
        mock_pool.enqueue_job.assert_awaited_once_with(
            "invalidate_cache_task",
            None,
            "prod:*",
        )
        mock_inline.assert_not_called()


# ── Tests for pool lifecycle ─────────────────────────────────────────────────


class TestArqPoolLifecycle:
    """Tests for the ARQ pool lifecycle helpers."""

    @pytest.mark.asyncio
    async def test_close_arq_pool_when_none(self):
        """Closing the pool when it's ``None`` should not raise."""
        await close_arq_pool()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_arq_pool_with_mock_pool(self):
        """Closing a mock pool should call ``close`` on it."""
        import app.tasks as tasks_module

        mock_pool = AsyncMock()
        tasks_module._arq_pool = mock_pool

        await close_arq_pool()

        assert tasks_module._arq_pool is None
        mock_pool.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_arq_pool_handles_close_error(self):
        """If pool.close() raises, the pool should still be set to None."""
        import app.tasks as tasks_module

        mock_pool = AsyncMock()
        mock_pool.close.side_effect = RuntimeError("Close failed")
        tasks_module._arq_pool = mock_pool

        await close_arq_pool()

        assert tasks_module._arq_pool is None  # Still cleaned up

    @pytest.mark.asyncio
    async def test_get_arq_pool_returns_none_no_redis(self):
        from app.tasks import _get_arq_pool

        with patch("app.tasks.settings.REDIS_URL", None):
            pool = await _get_arq_pool()
            assert pool is None
