"""Background task handlers for the SokoDigital API.

Tasks are designed to be run by the **ARQ** worker (``arq`` CLI or embedded
in a long-running process). Each function is a plain async function that
takes ``ctx`` as the first argument (the ARQ worker context).

Usage — start the worker::

    arq app.tasks.WorkerSettings

Or use the enqueue helpers from your route handlers::

    from app.tasks import enqueue_email
    await enqueue_email(to_email="a@b.com", template="welcome", context={...})
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services.email import send_email as _send_email

logger = logging.getLogger(__name__)


# ── Lazy Redis client for ARQ ───────────────────────────────────────────────


_arq_pool: Any = None


async def _get_arq_pool() -> Any:
    """Return a shared ARQ connection pool (lazy-init)."""
    global _arq_pool
    if _arq_pool is None and settings.REDIS_URL:
        try:
            import arq
            import redis.asyncio as aioredis

            r = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            _arq_pool = await arq.create_pool(r)
            logger.info("ARQ pool created")
        except Exception as exc:
            logger.warning("ARQ pool init failed: %s", exc)
            _arq_pool = False  # Sentinel
    elif _arq_pool is None:
        _arq_pool = False
    return _arq_pool if _arq_pool is not False else None


async def close_arq_pool() -> None:
    """Close the shared ARQ pool."""
    global _arq_pool
    if _arq_pool and _arq_pool is not False:
        try:
            _arq_pool.close()
            await _arq_pool.wait_closed()
        except Exception:
            pass
        _arq_pool = None


# ── Task functions ───────────────────────────────────────────────────────────


async def send_email_task(
    ctx: dict[str, Any],
    to_email: str,
    template_name: str,
    context: dict[str, Any] | None = None,
) -> bool:
    """Send an email in the background."""
    logger.info("Task: sending %s email to %s", template_name, to_email)
    try:
        return await _send_email(to_email, template_name, context or {})
    except Exception as exc:
        logger.error("Task: failed to send email to %s: %s", to_email, exc)
        return False


async def invalidate_cache_task(
    ctx: dict[str, Any],
    key_prefix: str | None = None,
    pattern: str | None = None,
) -> int:
    """Invalidate Redis cache entries by prefix or pattern.

    Parameters
    ----------
    key_prefix
        If given, delete all keys starting with this prefix.
    pattern
        If given, delete keys matching this glob pattern (e.g. ``cache:*``).

    Returns the number of deleted keys.
    """
    if not settings.REDIS_URL:
        logger.warning("Task: cache invalidation skipped — no Redis")
        return 0

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        async with r:
            if pattern:
                keys = await r.keys(pattern)
            elif key_prefix:
                keys = await r.keys(f"{key_prefix}*")
            else:
                keys = await r.keys("cache:*")

            if keys:
                deleted = await r.delete(*keys)
                logger.info("Task: invalidated %d cache keys", deleted)
                return deleted
            return 0
    except Exception as exc:
        logger.error("Task: cache invalidation error: %s", exc)
        return 0


# ── Enqueue helpers (call these from route handlers) ─────────────────────────


async def enqueue_email(
    to_email: str,
    template_name: str,
    context: dict[str, Any] | None = None,
) -> bool:
    """Enqueue an email for background delivery. Falls back to synchronous send."""
    try:
        import arq

        pool = await _get_arq_pool()
        if pool is not None:
            job = await pool.enqueue_job(
                "send_email_task",
                to_email,
                template_name,
                context or {},
            )
            logger.info("Enqueued email job %s", job.job_id)
            return True
    except ImportError:
        logger.warning("ARQ not installed, sending email synchronously")
    except Exception as exc:
        logger.warning("ARQ enqueue failed, sending email synchronously (%s)", exc)

    # Fallback: send directly
    return await _send_email(to_email, template_name, context or {})


async def enqueue_cache_invalidation(
    key_prefix: str | None = None,
    pattern: str | None = None,
) -> int:
    """Enqueue a cache invalidation task."""
    try:
        import arq

        pool = await _get_arq_pool()
        if pool is not None:
            job = await pool.enqueue_job(
                "invalidate_cache_task",
                key_prefix,
                pattern,
            )
            logger.info("Enqueued cache invalidation job %s", job.job_id)
            return 0  # Result unknown until task runs
    except ImportError:
        logger.warning("ARQ not installed, invalidating cache inline")
    except Exception as exc:
        logger.warning("ARQ enqueue failed, invalidating cache inline (%s)", exc)

    # Fallback: run inline (non-ctx version)
    return await invalidate_cache_task({}, key_prefix, pattern)


# ── ARQ WorkerSettings (used by ``arq run``) ─────────────────────────────────


def _get_redis_settings() -> Any:
    """Parse REDIS_URL into ARQ RedisSettings."""
    if not settings.REDIS_URL:
        raise RuntimeError(
            "REDIS_URL is not configured. Set it in your .env or environment."
        )

    try:
        from arq.connections import RedisSettings
        from urllib.parse import urlparse

        parsed = urlparse(settings.REDIS_URL)
        return RedisSettings(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            database=int(parsed.path.lstrip("/")) if parsed.path and parsed.path != "/" else 0,
            password=parsed.password,
        )
    except ImportError:
        raise RuntimeError("arq is not installed. Run: pip install arq")


class WorkerSettings:
    """ARQ worker configuration.

    Usage::

        arq app.tasks.WorkerSettings

    Or in Python::

        from arq import run_worker
        from app.tasks import WorkerSettings
        run_worker(WorkerSettings)
    """

    functions: list[Any] = [send_email_task, invalidate_cache_task]
    redis_settings: Any

    def __init__(self) -> None:
        self.redis_settings = _get_redis_settings()
