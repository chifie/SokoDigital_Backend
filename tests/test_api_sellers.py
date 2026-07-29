"""API integration tests for seller endpoints.

Tests seller onboarding, profile management, products listing,
and follower counts.

NOTE: These require a running PostgreSQL database with migrations applied.
"""

from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> tuple[str, str]:
    """Helper: register and login, return (token, email)."""
    import uuid

    unique = uuid.uuid4().hex[:8]
    user_data = {
        "email": f"sellertest_{unique}@example.com",
        "username": f"sellertest_{unique}",
        "password": "testpass123",
        "full_name": "Seller Tester",
    }
    await client.post("/api/v1/auth/register", json=user_data)
    login_resp = await client.post("/api/v1/auth/login", json={
        "identity": user_data["email"],
        "password": user_data["password"],
    })
    token = login_resp.json()["access_token"]
    return token, user_data["email"]


class TestSellersPublic:
    """Test public seller listing endpoints."""

    async def test_list_sellers(self, client: AsyncClient) -> None:
        """GET /sellers returns a list of sellers."""
        resp = await client.get("/api/v1/sellers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_list_sellers_is_public(self, client: AsyncClient) -> None:
        """Listing sellers does NOT require authentication."""
        resp = await client.get("/api/v1/sellers")
        assert resp.status_code == 200

    async def test_get_seller_not_found(self, client: AsyncClient) -> None:
        """GET /sellers/{id} with non-existent ID returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/sellers/{fake_id}")
        assert resp.status_code == 404


class TestSellerOnboarding:
    """Test seller onboarding flow."""

    async def test_onboard_seller_unauthorized(self, client: AsyncClient) -> None:
        """Onboarding without auth returns 401."""
        resp = await client.post("/api/v1/sellers/onboard", json={
            "store_name": "Test Store",
            "description": "A test store",
        })
        assert resp.status_code == 401

    async def test_onboard_seller_invalid_data(self, client: AsyncClient) -> None:
        """Onboarding with invalid data returns 422."""
        token, _ = await _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/sellers/onboard", json={}, headers=headers)
        assert resp.status_code == 422

    async def test_get_my_seller_profile_unauthorized(self, client: AsyncClient) -> None:
        """Getting own seller profile without auth returns 401."""
        resp = await client.get("/api/v1/sellers/me")
        assert resp.status_code == 401

    async def test_update_seller_unauthorized(self, client: AsyncClient) -> None:
        """Updating seller profile without auth returns 401."""
        resp = await client.put("/api/v1/sellers/me", json={"description": "Updated"})
        assert resp.status_code == 401


class TestSellerFollow:
    """Test seller follow/unfollow endpoints."""

    async def test_follow_seller_unauthorized(self, client: AsyncClient) -> None:
        """Following a seller without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.post(f"/api/v1/sellers/{fake_id}/toggle-follow")
        assert resp.status_code == 401

    async def test_follow_nonexistent_seller(self, client: AsyncClient) -> None:
        """Following a non-existent seller returns 404."""
        token, _ = await _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.post(
            f"/api/v1/sellers/{fake_id}/toggle-follow",
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_check_follow_status_unauthorized(self, client: AsyncClient) -> None:
        """Checking follow status without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/sellers/{fake_id}/is-following")
        assert resp.status_code == 401

    async def test_list_followers_unauthorized(self, client: AsyncClient) -> None:
        """Listing followers without auth returns 401."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/sellers/{fake_id}/followers")
        assert resp.status_code == 401

    async def test_list_following_unauthorized(self, client: AsyncClient) -> None:
        """List who I'm following without auth returns 401."""
        resp = await client.get("/api/v1/sellers/i-follow")
        assert resp.status_code == 401
