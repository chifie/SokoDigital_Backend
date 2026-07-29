"""Pytest fixtures for testing the SokoDigital API.

These fixtures override the database to use an in-memory SQLite database,
allowing tests to run without a PostgreSQL instance.
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models.base import Base

# Set testing flags BEFORE importing app modules
os.environ["SOKO_TESTING"] = "1"
os.environ["SOKO_TEST_DATABASE_URL"] = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio as the async backend for pytest-asyncio."""
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a fresh SQLite in-memory database engine for the test session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session per test with a transaction that rolls back."""
    # Use a connection-level transaction that gets rolled back after each test
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client with the test database session injected."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def sample_product_data() -> dict[str, Any]:
    """Sample product creation data."""
    return {
        "name": "Test Product",
        "slug": "test-product",
        "description": "A test product for unit testing",
        "price": 29.99,
        "currency": "TZS",
        "condition": "new",
        "quantity": 100,
        "images": [],
    }


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Sample user registration data."""
    import uuid

    unique = uuid.uuid4().hex[:8]
    return {
        "email": f"test_{unique}@example.com",
        "username": f"testuser_{unique}",
        "password": "testpass123",
        "full_name": "Test User",
    }


@pytest.fixture
def sample_login_data(sample_user_data: dict[str, Any]) -> dict[str, Any]:
    """Sample login data based on sample_user_data."""
    return {
        "identity": sample_user_data["email"],
        "password": sample_user_data["password"],
    }
