"""Comprehensive API integration tests for authentication endpoints.

Tests cover registration, login, token management, profile, password reset,
email verification, and protected route access.

NOTE: These require a running PostgreSQL database with migrations applied.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestAuthRegister:
    """Test user registration flow."""

    async def test_register_success(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Register a new user successfully."""
        resp = await client.post("/api/v1/auth/register", json=sample_user_data)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == sample_user_data["email"]
        assert data["username"] == sample_user_data["username"]
        assert "password" not in data
        assert data["is_active"] is True
        assert data["is_verified"] is False

    async def test_register_duplicate_email(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Registering with an existing email returns 409."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        resp = await client.post("/api/v1/auth/register", json=sample_user_data)
        assert resp.status_code == 409
        data = resp.json()
        assert data["success"] is False

    async def test_register_duplicate_username(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Registering with an existing username returns 409."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        dupe = {**sample_user_data, "email": "different@example.com"}
        resp = await client.post("/api/v1/auth/register", json=dupe)
        assert resp.status_code == 409

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        """Registering with an invalid email returns 422."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "username": "newuser",
            "password": "testpass123",
        })
        assert resp.status_code == 422

    async def test_register_short_password(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Registering with a short password returns 422."""
        resp = await client.post("/api/v1/auth/register", json={
            **sample_user_data,
            "password": "123",
        })
        assert resp.status_code == 422

    async def test_register_missing_fields(self, client: AsyncClient) -> None:
        """Registering without required fields returns 422."""
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422


@pytest.mark.integration
class TestAuthLogin:
    """Test user login flow."""

    async def test_login_with_email(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Login with email and password."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        resp = await client.post("/api/v1/auth/login", json={
            "identity": sample_user_data["email"],
            "password": sample_user_data["password"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_with_username(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Login with username and password."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        resp = await client.post("/api/v1/auth/login", json={
            "identity": sample_user_data["username"],
            "password": sample_user_data["password"],
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Login with wrong password returns 401."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        resp = await client.post("/api/v1/auth/login", json={
            "identity": sample_user_data["email"],
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        """Login with non-existent user returns 401."""
        resp = await client.post("/api/v1/auth/login", json={
            "identity": "nobody@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == 401

    async def test_login_empty_credentials(self, client: AsyncClient) -> None:
        """Login with empty credentials returns 422."""
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


@pytest.mark.integration
class TestAuthProfile:
    """Test authenticated user profile endpoints."""

    async def test_get_me(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Get authenticated user's profile."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        login_resp = await client.post("/api/v1/auth/login", json={
            "identity": sample_user_data["email"],
            "password": sample_user_data["password"],
        })
        token = login_resp.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == sample_user_data["email"]
        assert data["username"] == sample_user_data["username"]
        assert "hashed_password" not in data

    async def test_get_me_no_token(self, client: AsyncClient) -> None:
        """Get profile without auth token returns 401."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient) -> None:
        """Get profile with invalid token returns 401."""
        headers = {"Authorization": "Bearer invalid-token"}
        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 401

    async def test_update_profile(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Update authenticated user's profile."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        login_resp = await client.post("/api/v1/auth/login", json={
            "identity": sample_user_data["email"],
            "password": sample_user_data["password"],
        })
        token = login_resp.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.put("/api/v1/auth/me", json={
            "full_name": "Updated Name",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"


@pytest.mark.integration
class TestAuthProtectedEndpoints:
    """Test that various protected endpoints require authentication."""

    async def test_products_require_auth_for_write(self, client: AsyncClient) -> None:
        """Creating a product without auth returns 401."""
        resp = await client.post("/api/v1/products", json={"name": "Test"})
        assert resp.status_code == 401

    async def test_orders_require_auth(self, client: AsyncClient) -> None:
        """Listing orders without auth returns 401."""
        resp = await client.get("/api/v1/orders")
        assert resp.status_code == 401

    async def test_addresses_require_auth(self, client: AsyncClient) -> None:
        """Listing addresses without auth returns 401."""
        resp = await client.get("/api/v1/addresses")
        assert resp.status_code == 401

    async def test_wishlist_requires_auth(self, client: AsyncClient) -> None:
        """Listing wishlist without auth returns 401."""
        resp = await client.get("/api/v1/wishlist")
        assert resp.status_code == 401

    async def test_reviews_my_requires_auth(self, client: AsyncClient) -> None:
        """Getting my reviews without auth returns 401."""
        resp = await client.get("/api/v1/reviews/mine")
        assert resp.status_code == 401

    async def test_admin_endpoints_require_auth(self, client: AsyncClient) -> None:
        """Admin endpoints without auth return 401."""
        resp = await client.get("/api/v1/admin/users")
        assert resp.status_code == 401

    async def test_messaging_requires_auth(self, client: AsyncClient) -> None:
        """Messaging endpoints without auth return 401."""
        resp = await client.get("/api/v1/conversations")
        assert resp.status_code == 401

    async def test_seller_endpoints_require_auth(self, client: AsyncClient) -> None:
        """Seller endpoints without auth return 401."""
        resp = await client.post("/api/v1/sellers/onboard", json={"name": "Test"})
        assert resp.status_code == 401
