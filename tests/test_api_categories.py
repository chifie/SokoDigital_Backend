"""API integration tests for category endpoints.

Tests both public listing and admin CRUD operations.

NOTE: These require a running PostgreSQL database with migrations applied.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestCategoriesPublic:
    """Test public category listing endpoints."""

    async def test_list_categories(self, client: AsyncClient) -> None:
        """GET /categories returns a list of categories."""
        resp = await client.get("/api/v1/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_list_categories_with_pagination(self, client: AsyncClient) -> None:
        """GET /categories supports skip/limit pagination."""
        resp = await client.get("/api/v1/categories?skip=0&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) <= 10

    async def test_get_category_by_slug(self, client: AsyncClient) -> None:
        """GET /categories/slug/{slug} returns a category if it exists."""
        resp = await client.get("/api/v1/categories/slug/electronics")
        if resp.status_code == 200:
            data = resp.json()
            assert data["slug"] == "electronics"
        else:
            assert resp.status_code == 404

    async def test_get_category_by_slug_not_found(self, client: AsyncClient) -> None:
        """GET /categories/slug/{slug} with non-existent slug returns 404."""
        resp = await client.get("/api/v1/categories/slug/nonexistent-category")
        assert resp.status_code == 404

    async def test_get_category_tree(self, client: AsyncClient) -> None:
        """GET /categories/tree returns a nested tree structure."""
        resp = await client.get("/api/v1/categories/tree")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_categories_no_auth_required(self, client: AsyncClient) -> None:
        """Listing categories does NOT require authentication."""
        resp = await client.get("/api/v1/categories")
        assert resp.status_code == 200

    async def test_get_single_category_not_found(self, client: AsyncClient) -> None:
        """GET /categories/{id} with non-existent ID returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/categories/{fake_id}")
        assert resp.status_code == 404

    async def test_get_category_products_empty(self, client: AsyncClient) -> None:
        """GET /categories/{id}/products with non-existent category returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/categories/{fake_id}/products")
        assert resp.status_code == 404


@pytest.mark.integration
class TestCategoriesAdmin:
    """Test admin category management endpoints."""

    async def test_create_category_unauthorized(self, client: AsyncClient) -> None:
        """Creating a category without auth returns 401."""
        resp = await client.post("/api/v1/categories", json={
            "name": "Test Category",
            "slug": "test-category",
        })
        assert resp.status_code == 401

    async def test_update_category_unauthorized(self, client: AsyncClient) -> None:
        """Updating a category without auth returns 401."""
        resp = await client.put("/api/v1/categories/00000000-0000-0000-0000-000000000000", json={"name": "Updated"})
        assert resp.status_code == 401

    async def test_delete_category_unauthorized(self, client: AsyncClient) -> None:
        """Deleting a category without auth returns 401."""
        resp = await client.delete("/api/v1/categories/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 401
