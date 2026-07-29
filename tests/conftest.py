"""Pytest fixtures for testing the SokoDigital API."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the async backend for pytest-asyncio."""
    return "asyncio"


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing the FastAPI app."""
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
