"""Pytest fixtures for testing the SokoDigital API.

Non-database tests (pagination, rate limiting, seller follow logic) work
without any database setup.

Integration tests (email verification, auth flows) require a PostgreSQL
instance with migrations applied. Set the ``DATABASE_URL`` env var to
point to your test database.
"""

import os
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the async backend for pytest-asyncio."""
    return "asyncio"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client against the live FastAPI app.

    Requires a running PostgreSQL database. Set ``DATABASE_URL`` env var
    to configure the connection.
    """
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
