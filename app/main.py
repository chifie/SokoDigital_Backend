from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models.base import Base


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Lifecycle handler - creates tables on startup, disposes engine on shutdown."""
    # Create all tables on startup (for development convenience)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Dispose of the connection pool on shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

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
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}


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
from app.api.v1 import sellers as sellers_router
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
app.include_router(sellers_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(wishlist_router.router, prefix=settings.API_V1_PREFIX)
