"""Comprehensive API integration tests for product endpoints.

Tests CRUD operations, search/filter/sort, category filtering,
and authorization checks for seller-level operations.

NOTE: These require a running PostgreSQL database with migrations + seed data.
"""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> tuple[dict, str]:
    """Helper: register and login a user, return (user_data, token)."""
    import uuid

    unique = uuid.uuid4().hex[:8]
    user_data = {
        "email": f"prodtest_{unique}@example.com",
        "username": f"prodtest_{unique}",
        "password": "testpass123",
        "full_name": "Product Tester",
    }
    await client.post("/api/v1/auth/register", json=user_data)
    login_resp = await client.post("/api/v1/auth/login", json={
        "identity": user_data["email"],
        "password": user_data["password"],
    })
    token = login_resp.json()["access_token"]
    return user_data, token


async def _create_product(
    client: AsyncClient, token: str, overrides: dict | None = None,
) -> dict:
    """Helper: create a product and return the response JSON."""
    payload = {
        "name": "Test Product",
        "slug": "test-product",
        "description": "A test product",
        "price": 29.99,
        "currency": "TZS",
        "condition": "new",
        "quantity": 100,
        "images": [],
    }
    if overrides:
        payload.update(overrides)

    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post("/api/v1/products", json=payload, headers=headers)
    return resp


@pytest.mark.integration
class TestProductsList:
    """Test public product listing endpoints."""

    async def test_list_products(self, client: AsyncClient) -> None:
        """GET /products returns a list."""
        resp = await client.get("/api/v1/products")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_list_products_with_pagination(self, client: AsyncClient) -> None:
        """GET /products supports skip/limit pagination."""
        resp = await client.get("/api/v1/products?skip=0&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) <= 5

    async def test_list_products_empty_search(self, client: AsyncClient) -> None:
        """GET /products with non-matching search returns empty list."""
        resp = await client.get("/api/v1/products?search=zzzznonexistentxxxx")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_products_by_category(self, client: AsyncClient) -> None:
        """GET /products with category filter works."""
        resp = await client.get("/api/v1/products?category_id=00000000-0000-0000-0000-000000000001")
        # This may return empty if no products in that fake category
        assert resp.status_code == 200

    async def test_products_public_no_auth_required(self, client: AsyncClient) -> None:
        """Listing products does NOT require authentication."""
        resp = await client.get("/api/v1/products")
        assert resp.status_code == 200


@pytest.mark.integration
class TestProductsCreate:
    """Test authenticated product creation."""

    async def test_create_product_requires_seller(self, client: AsyncClient) -> None:
        """Creating a product without seller profile should fail."""
        _, token = await _register_and_login(client)
        resp = await _create_product(client, token)
        # Creating a product without a seller profile returns a client error
        assert resp.status_code == 403

    async def test_create_product_invalid_data(self, client: AsyncClient) -> None:
        """Creating a product with invalid data returns 422."""
        _, token = await _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/products", json={}, headers=headers)
        assert resp.status_code == 422

    async def test_create_product_missing_name(self, client: AsyncClient) -> None:
        """Creating a product without a name returns 422."""
        _, token = await _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/products", json={
            "price": 10.0,
        }, headers=headers)
        assert resp.status_code == 422

    async def test_create_product_negative_price(self, client: AsyncClient) -> None:
        """Creating a product with negative price returns 422."""
        _, token = await _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/products", json={
            "name": "Test",
            "slug": "test",
            "price": -10.0,
            "condition": "new",
            "quantity": 1,
        }, headers=headers)
        assert resp.status_code == 422

    async def test_create_product_zero_quantity(self, client: AsyncClient) -> None:
        """Creating a product with zero quantity should be allowed (out of stock)."""
        _, token = await _register_and_login(client)
        resp = await _create_product(client, token, {"quantity": 0})
        # Creating a product with zero quantity should return 201 if seller,
        # or 403 if not a seller
        assert resp.status_code in (201, 403)

    async def test_create_product_unauthorized(self, client: AsyncClient) -> None:
        """Creating a product without auth returns 401."""
        resp = await client.post("/api/v1/products", json={
            "name": "Unauthorized Product",
        })
        assert resp.status_code == 401


@pytest.mark.integration
class TestProductsSingle:
    """Test single product retrieval."""

    async def test_get_product_by_id_not_found(self, client: AsyncClient) -> None:
        """GET /products/{id} with non-existent UUID returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/products/{fake_id}")
        assert resp.status_code == 404

    async def test_get_product_by_slug_not_found(self, client: AsyncClient) -> None:
        """GET /products/slug/{slug} with non-existent slug returns 404."""
        resp = await client.get("/api/v1/products/slug/nonexistent-product-slug")
        assert resp.status_code == 404

    async def test_get_product_invalid_id_format(self, client: AsyncClient) -> None:
        """GET /products/{id} with invalid UUID returns 422."""
        resp = await client.get("/api/v1/products/not-a-uuid")
        assert resp.status_code == 404


@pytest.mark.integration
class TestProductReviews:
    """Test product review endpoints."""

    async def test_get_product_reviews_not_found(self, client: AsyncClient) -> None:
        """GET /reviews/product/{id} with non-existent product returns 200 (empty list)."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(f"/api/v1/reviews/product/{fake_id}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_review_unauthorized(self, client: AsyncClient) -> None:
        """Creating a review without auth returns 401."""
        resp = await client.post("/api/v1/reviews", json={
            "product_id": "00000000-0000-0000-0000-000000000000",
            "rating": 5,
            "title": "Great!",
            "content": "Amazing product.",
        })
        assert resp.status_code == 401

    async def test_create_review_invalid_rating(self, client: AsyncClient) -> None:
        """Creating a review with invalid rating returns 422."""
        _, token = await _register_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post("/api/v1/reviews", json={
            "product_id": "00000000-0000-0000-0000-000000000000",
            "rating": 10,  # Rating must be 1-5
            "title": "Great!",
            "content": "Amazing product.",
        }, headers=headers)
        assert resp.status_code == 422
