"""Tests for the email verification flow.

Note: These tests validate the logic of the verification endpoints
without actually sending emails (SMTP is not configured in test mode).
"""

from httpx import AsyncClient


class TestEmailVerification:
    """Test suite for email verification endpoints."""

    async def test_register_returns_user(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Registration should return user data without password."""
        response = await client.post("/api/v1/auth/register", json=sample_user_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == sample_user_data["email"]
        assert data["username"] == sample_user_data["username"]
        assert "password" not in data  # password should never be returned
        assert data["is_verified"] is False

    async def test_register_duplicate_email(self, client: AsyncClient, sample_user_data: dict) -> None:
        """Registering with an existing email should return 409."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        response = await client.post("/api/v1/auth/register", json=sample_user_data)
        assert response.status_code == 409

    async def test_login_after_register(self, client: AsyncClient, sample_user_data: dict, sample_login_data: dict) -> None:
        """Registered user should be able to login."""
        await client.post("/api/v1/auth/register", json=sample_user_data)
        response = await client.post("/api/v1/auth/login", json=sample_login_data)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_verify_email_with_invalid_token(self, client: AsyncClient) -> None:
        """Verifying with an invalid token should return 400."""
        response = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": "invalid-token", "email": "nonexistent@example.com"},
        )
        assert response.status_code == 404

    async def test_resend_verification_nonexistent_email(self, client: AsyncClient) -> None:
        """Resending verification for a non-existent email should return 404."""
        response = await client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 404
