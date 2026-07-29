import logging
from contextlib import asynccontextmanager
from pathlib import Path

from datetime import datetime, timezone

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


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Lifecycle handler - creates tables on startup, disposes engine on shutdown."""
    logger.info("Starting up %s v%s (env=%s)", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    # Create all tables on startup (for development convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Global exception handlers (wrap errors in a consistent JSON envelope)
# ---------------------------------------------------------------------------
from app.utils.response import register_error_handlers

register_error_handlers(app)

# ---------------------------------------------------------------------------
# Request ID middleware — attach a unique ID to every request
# ---------------------------------------------------------------------------
from app.middleware.request_id import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)  # type: ignore[arg-type]

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
    Used by Docker HEALTHCHECK and monitoring systems.
    """
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "app_name": settings.APP_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.ENVIRONMENT,
    }


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
app.include_router(wishlist_router.router, prefix=settings.API_V1_PREFIX)
