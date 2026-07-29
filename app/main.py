import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from datetime import datetime, timezone

import sqlalchemy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine
from app.models.base import Base

# Set up structured logging before anything else
from app.middleware.request_id import setup_logging

setup_logging()
logger = logging.getLogger("app")


# ---------------------------------------------------------------------------
# Sentry error monitoring (optional — configured via SENTRY_DSN env var)
# ---------------------------------------------------------------------------
def setup_sentry() -> None:
    """Initialize Sentry SDK if ``SENTRY_DSN`` is configured."""
    if not settings.SENTRY_DSN:
        logger.debug("Sentry DSN not configured — skipping Sentry initialization")
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=settings.APP_VERSION,
            traces_sample_rate=0.2,  # Sample 20% of transactions in production
            send_default_pii=False,  # Don't send user data by default
        )
        logger.info(
            "Sentry initialized (env=%s, release=%s, sample_rate=0.2)",
            settings.ENVIRONMENT,
            settings.APP_VERSION,
        )
    except ImportError:
        logger.warning(
            "sentry-sdk not installed — install with: pip install sentry-sdk"
        )
    except Exception as exc:
        logger.error("Failed to initialize Sentry: %s", exc)


setup_sentry()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Lifecycle handler - creates tables on startup, disposes engine on shutdown."""
    logger.info("Starting up %s v%s (env=%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    # Create all tables on startup (for development convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Configure Meilisearch index if URL is set
    if settings.MEILISEARCH_URL:
        try:
            from app.services.search import configure_index
            await configure_index()
        except Exception:
            logger.warning("Failed to configure Meilisearch index", exc_info=True)

    yield
    # Dispose of the connection pool on shutdown
    await engine.dispose()
    # Close the rate limiter connection (e.g., Redis) if applicable
    from app.middleware.rate_limit import _limiter
    await _limiter.close()
    # Close the cache connection
    from app.middleware.cache import close_cache
    await close_cache()
    # Close the ARQ pool if open
    try:
        from app.tasks import close_arq_pool
        await close_arq_pool()
    except ImportError:
        pass
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    SokoDigital Marketplace API — a full-featured e-commerce backend.

    ## Rate Limiting
    Auth endpoints are rate-limited to **10 requests/minute** per IP.
    Upload endpoints are rate-limited to **20 requests/minute** per IP.
    All other endpoints are limited to **100 requests/minute** per IP.
    When rate-limited, the response includes `Retry-After`, `X-RateLimit-Limit`,
    and `X-RateLimit-Remaining` headers.

    ## Response Caching
    Successful `GET` responses are cached in Redis for **60 seconds** (default).
    Cache hits return `X-Cache: HIT`; misses return `X-Cache: MISS`.
    Cached responses bypass the route handler entirely for faster response times.

    ## Authentication
    Most endpoints require a JWT access token sent as `Authorization: Bearer <token>`.
    Obtain a token via `POST /api/v1/auth/login`.

    ## Error Format
    All errors follow a consistent JSON envelope:
    ```json
    {"success": false, "message": "...", "detail": "...", "error": "..."}
    ```
    The `detail` key is preserved for backward compatibility with standard FastAPI clients.
    """.strip(),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "SokoDigital Support",
        "email": "support@sokodigital.com",
    },
    license_info={
        "name": "MIT",
    },
)

# ---------------------------------------------------------------------------
# Global exception handlers (wrap errors in a consistent JSON envelope)
# ---------------------------------------------------------------------------
from app.utils.response import register_error_handlers

register_error_handlers(app)

# If Sentry is active, attach a before-send callback to scrub sensitive data
if settings.SENTRY_DSN and "sentry_sdk" in sys.modules:
    import sentry_sdk

    def _before_send(event: dict, hint: dict) -> dict | None:
        """Scrub sensitive fields from Sentry events before sending."""
        if "request" in event and "data" in event["request"]:
            data = event["request"]["data"]
            if isinstance(data, dict):
                for field in ("password", "token", "secret", "authorization"):
                    if field in data:
                        data[field] = "[scrubbed]"
        return event

    sentry_sdk.set_before_send_callback(_before_send)  # type: ignore[arg-type]
    logger.debug("Sentry before-send callback registered (scrubs passwords)")

# ---------------------------------------------------------------------------
# API versioning middleware — adds version & deprecation headers
# ---------------------------------------------------------------------------
from app.middleware.versioning import APIVersioningMiddleware

app.add_middleware(APIVersioningMiddleware, latest_version=settings.API_LATEST_VERSION)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# Request ID middleware — attach a unique ID to every request
# ---------------------------------------------------------------------------
from app.middleware.request_id import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# OpenTelemetry tracing middleware (before other middleware to capture full span)
# ---------------------------------------------------------------------------
from app.middleware.tracing import TracingMiddleware, setup_tracing

setup_tracing(service_name=settings.APP_NAME)
app.add_middleware(TracingMiddleware)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# Metrics middleware — Prometheus request tracking (before CORS so it sees all)
# ---------------------------------------------------------------------------
from app.middleware.metrics import MetricsMiddleware, metrics_endpoint

app.add_middleware(MetricsMiddleware)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# Response cache middleware (Redis-backed, caches GET responses)
# ---------------------------------------------------------------------------
from app.middleware.cache import CacheMiddleware

app.add_middleware(CacheMiddleware, default_ttl=settings.CACHE_DEFAULT_TTL)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# CORS — allow the frontend origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check & API metadata
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns the current service status, version, and a timestamp.
    Pings PostgreSQL and Redis (if configured) to verify connectivity.
    Used by Docker HEALTHCHECK and monitoring systems.

    Returns ``503 Service Unavailable`` if any required dependency is down.
    """
    from fastapi.responses import JSONResponse

    checks: dict[str, str | bool] = {
        "database": False,
        "redis": False,
    }

    # ── Ping PostgreSQL ─────────────────────────────────────────────────
    try:
        async with engine.connect() as conn:
            await conn.execute(
                sqlalchemy.text("SELECT 1")
            )
        checks["database"] = True
    except Exception as exc:
        checks["database"] = f"unreachable: {exc}"

    # ── Ping Redis (if configured) ──────────────────────────────────────
    if settings.REDIS_URL:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await r.ping()
            await r.close()
            checks["redis"] = True
        except Exception as exc:
            checks["redis"] = f"unreachable: {exc}"
    else:
        checks["redis"] = "not configured"

    all_ok = (
        checks["database"] is True
        and (checks["redis"] is True or checks["redis"] == "not configured")
    )

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if all_ok else "degraded",
            "version": settings.APP_VERSION,
            "app_name": settings.APP_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": settings.ENVIRONMENT,
            "checks": checks,
        },
    )


@app.get("/api", summary="API version information")
async def api_info():
    """
    Return metadata about the API — version, available endpoints, and docs links.
    """
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": f"{settings.API_V1_PREFIX}/openapi.json",
        "metrics": "/metrics",
        "api_prefix": settings.API_V1_PREFIX,
    }


# ---------------------------------------------------------------------------
# Metrics endpoint (serves Prometheus-format data at /metrics)
# ---------------------------------------------------------------------------
app.add_api_route("/metrics", metrics_endpoint, include_in_schema=False)


# ---------------------------------------------------------------------------
# Static files (serving uploaded files)
# ---------------------------------------------------------------------------
upload_dir = Path(settings.UPLOAD_DIR)
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


# ---------------------------------------------------------------------------
# API v1 routers
# ---------------------------------------------------------------------------
from app.api.v1 import addresses as addresses_router
from app.api.v1 import admin as admin_router
from app.api.v1 import ai_extra as ai_extra_router
from app.api.v1 import auth as auth_router
from app.api.v1 import categories as categories_router
from app.api.v1 import engagement as engagement_router
from app.api.v1 import messaging as messaging_router
from app.api.v1 import orders as orders_router
from app.api.v1 import products as products_router
from app.api.v1 import reviews as reviews_router
from app.api.v1 import seller_follow as seller_follow_router
from app.api.v1 import sellers as sellers_router
from app.api.v1 import uploads as uploads_router
from app.api.v1 import webhooks as webhooks_router
from app.api.v1 import wishlist as wishlist_router

app.include_router(addresses_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_extra_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(categories_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(messaging_router.router, prefix=settings.API_V1_PREFIX)

# Engagement sub-routers
app.include_router(engagement_router.banner_router, prefix=settings.API_V1_PREFIX)
app.include_router(engagement_router.coupon_router, prefix=settings.API_V1_PREFIX)
app.include_router(engagement_router.flash_sale_router, prefix=settings.API_V1_PREFIX)
app.include_router(engagement_router.notification_router, prefix=settings.API_V1_PREFIX)

app.include_router(orders_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(products_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(reviews_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(seller_follow_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(sellers_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(uploads_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(webhooks_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(wishlist_router.router, prefix=settings.API_V1_PREFIX)
