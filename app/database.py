import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# Allow overriding the database URL via environment (used by tests)
def _get_database_url() -> str:
    """Return the database URL, respecting the TEST_DATABASE_URL override."""
    return os.environ.get(
        "SOKO_TEST_DATABASE_URL",
        settings.TEST_DATABASE_URL if os.environ.get("SOKO_TESTING") else settings.DATABASE_URL,
    )


engine = create_async_engine(
    _get_database_url(),
    echo=settings.DEBUG,
    pool_size=20 if not os.environ.get("SOKO_TESTING") else 5,
    max_overflow=10 if not os.environ.get("SOKO_TESTING") else 0,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
