"""seed_sample_data

Revision ID: a1b2c3d4e5f6
Revises: 92c79a66f099
Create Date: 2026-07-29 13:00:00.000000

Insert seed data for local development:
- Admin user (admin@sokodigital.com / admin123)
- Seller user (seller@sokodigital.com / seller123)
- Customer user (customer@example.com / customer123)
- Seller profile (TechZone Africa)
- 6 product categories
- 4 sample products
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone
import uuid


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '92c79a66f099'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _uuid(val: str) -> uuid.UUID:
    """Deterministic UUID from a hex string for reproducibility."""
    return uuid.UUID(hex=val)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str) -> str:
    """Generate a bcrypt hash for the given password at migration time.

    Uses passlib (already in requirements.txt) to create a real bcrypt
    hash so the seed users can actually log in.
    """
    from passlib.hash import bcrypt
    return bcrypt.hash(password)


# ── Data ─────────────────────────────────────────────────────────────────────

ADMIN_ID = _uuid("00000000-0000-0000-0000-000000000001")
SELLER_USER_ID = _uuid("00000000-0000-0000-0000-000000000002")
SELLER_ID = _uuid("00000000-0000-0000-0000-000000000010")

CATEGORIES = [
    {"id": _uuid("10000000-0000-0000-0000-000000000001"), "name": "Electronics", "slug": "electronics", "description": "Phones, laptops, tablets, and accessories", "icon": "laptop", "sort_order": 1},
    {"id": _uuid("10000000-0000-0000-0000-000000000002"), "name": "Fashion", "slug": "fashion", "description": "Clothing, shoes, and accessories", "icon": "shirt", "sort_order": 2},
    {"id": _uuid("10000000-0000-0000-0000-000000000003"), "name": "Home & Garden", "slug": "home-garden", "description": "Furniture, decor, and garden supplies", "icon": "home", "sort_order": 3},
    {"id": _uuid("10000000-0000-0000-0000-000000000004"), "name": "Beauty & Health", "slug": "beauty-health", "description": "Skincare, makeup, and wellness products", "icon": "sparkles", "sort_order": 4},
    {"id": _uuid("10000000-0000-0000-0000-000000000005"), "name": "Sports & Outdoors", "slug": "sports-outdoors", "description": "Sports equipment and outdoor gear", "icon": "activity", "sort_order": 5},
    {"id": _uuid("10000000-0000-0000-0000-000000000006"), "name": "Books & Media", "slug": "books-media", "description": "Books, e-books, and digital media", "icon": "book", "sort_order": 6},
]

PRODUCTS = [
    {
        "id": _uuid("20000000-0000-0000-0000-000000000001"),
        "name": "Wireless Bluetooth Headphones",
        "slug": "wireless-bluetooth-headphones",
        "description": "Premium noise-cancelling wireless headphones with 30-hour battery life. Features deep bass, comfortable over-ear design, and built-in microphone for calls.",
        "price": 85000.0,
        "currency": "TZS",
        "condition": "new",
        "quantity": 50,
        "sold": 120,
        "category_id": _uuid("10000000-0000-0000-0000-000000000001"),
        "seller_id": SELLER_ID,
        "status": "active",
        "featured": True,
        "trending": True,
        "rating": 4.5,
        "review_count": 28,
        "tags": ["electronics", "audio", "wireless", "headphones"],
    },
    {
        "id": _uuid("20000000-0000-0000-0000-000000000002"),
        "name": "Smartphone Pro X",
        "slug": "smartphone-pro-x",
        "description": "Flagship smartphone with 6.7\" AMOLED display, 128GB storage, 48MP triple camera, and 5G connectivity.",
        "price": 450000.0,
        "currency": "TZS",
        "condition": "new",
        "quantity": 25,
        "sold": 200,
        "category_id": _uuid("10000000-0000-0000-0000-000000000001"),
        "seller_id": SELLER_ID,
        "status": "active",
        "featured": True,
        "trending": False,
        "rating": 4.8,
        "review_count": 156,
        "tags": ["electronics", "phones", "smartphone", "5g"],
    },
    {
        "id": _uuid("20000000-0000-0000-0000-000000000003"),
        "name": "Premium Cotton T-Shirt",
        "slug": "premium-cotton-t-shirt",
        "description": "100% organic cotton t-shirt. Comfortable, breathable, and available in multiple colors. Perfect for casual wear.",
        "price": 15000.0,
        "currency": "TZS",
        "condition": "new",
        "quantity": 200,
        "sold": 450,
        "category_id": _uuid("10000000-0000-0000-0000-000000000002"),
        "seller_id": SELLER_ID,
        "status": "active",
        "featured": False,
        "trending": True,
        "rating": 4.2,
        "review_count": 89,
        "tags": ["fashion", "clothing", "cotton", "t-shirt"],
    },
    {
        "id": _uuid("20000000-0000-0000-0000-000000000004"),
        "name": "Modern Desk Lamp",
        "slug": "modern-desk-lamp",
        "description": "LED desk lamp with adjustable brightness, color temperature control, and USB charging port. Eye-care design for long work sessions.",
        "price": 35000.0,
        "currency": "TZS",
        "condition": "new",
        "quantity": 75,
        "sold": 60,
        "category_id": _uuid("10000000-0000-0000-0000-000000000003"),
        "seller_id": SELLER_ID,
        "status": "active",
        "featured": False,
        "trending": False,
        "rating": 4.6,
        "review_count": 34,
        "tags": ["home", "lighting", "led", "desk-lamp"],
    },
]


def upgrade() -> None:
    connection = op.get_bind()

    # ── Generate real bcrypt hashes at migration time ──────────────────────
    # Users can log in with the passwords shown in the docstring.
    admin_hash = _hash_password("admin123")
    seller_hash = _hash_password("seller123")
    customer_hash = _hash_password("customer123")

    # ── 1. Admin User ──────────────────────────────────────────────────────
    connection.execute(
        sa.text(
            """
            INSERT INTO users (id, email, username, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at)
            VALUES (:id, :email, :username, :password, :full_name, :role, :active, :verified, :now, :now)
            ON CONFLICT (email) DO NOTHING
            """
        ),
        {
            "id": ADMIN_ID,
            "email": "admin@sokodigital.com",
            "username": "admin",
            "password": admin_hash,
            "full_name": "Admin User",
            "role": "admin",
            "active": True,
            "verified": True,
            "now": _now(),
        },
    )

    # ── 2. Seller User ────────────────────────────────────────────────────
    connection.execute(
        sa.text(
            """
            INSERT INTO users (id, email, username, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at)
            VALUES (:id, :email, :username, :password, :full_name, :role, :active, :verified, :now, :now)
            ON CONFLICT (email) DO NOTHING
            """
        ),
        {
            "id": SELLER_USER_ID,
            "email": "seller@sokodigital.com",
            "username": "techseller",
            "password": seller_hash,
            "full_name": "Tech Seller",
            "role": "seller",
            "active": True,
            "verified": True,
            "now": _now(),
        },
    )

    # ── 3. Customer User ──────────────────────────────────────────────────
    customer_id = _uuid("00000000-0000-0000-0000-000000000003")
    connection.execute(
        sa.text(
            """
            INSERT INTO users (id, email, username, hashed_password, full_name, role, is_active, is_verified, created_at, updated_at)
            VALUES (:id, :email, :username, :password, :full_name, :role, :active, :verified, :now, :now)
            ON CONFLICT (email) DO NOTHING
            """
        ),
        {
            "id": customer_id,
            "email": "customer@example.com",
            "username": "customer1",
            "password": customer_hash,
            "full_name": "Test Customer",
            "role": "customer",
            "active": True,
            "verified": True,
            "now": _now(),
        },
    )

    # ── 4. Seller Profile ─────────────────────────────────────────────────
    connection.execute(
        sa.text(
            """
            INSERT INTO sellers (id, user_id, store_name, store_slug, description, location, is_verified, is_active, created_at, updated_at)
            VALUES (:id, :user_id, :store_name, :slug, :desc, :location, :verified, :active, :now, :now)
            ON CONFLICT (store_slug) DO NOTHING
            """
        ),
        {
            "id": SELLER_ID,
            "user_id": SELLER_USER_ID,
            "store_name": "TechZone Africa",
            "slug": "techzone-africa",
            "desc": "Your premier destination for electronics and tech accessories in Tanzania. Quality products, fast delivery, excellent customer service.",
            "location": "Dar es Salaam, Tanzania",
            "verified": True,
            "active": True,
            "now": _now(),
        },
    )

    # ── 5. Categories ─────────────────────────────────────────────────────
    for cat in CATEGORIES:
        connection.execute(
            sa.text(
                """
                INSERT INTO categories (id, name, slug, description, icon, sort_order, is_active, created_at, updated_at)
                VALUES (:id, :name, :slug, :desc, :icon, :sort, :active, :now, :now)
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {
                "id": cat["id"],
                "name": cat["name"],
                "slug": cat["slug"],
                "desc": cat["description"],
                "icon": cat["icon"],
                "sort": cat["sort_order"],
                "active": True,
                "now": _now(),
            },
        )

    # ── 6. Products ────────────────────────────────────────────────────────
    for prod in PRODUCTS:
        connection.execute(
            sa.text(
                """
                INSERT INTO products (id, name, slug, description, price, currency, condition, quantity, sold, category_id, seller_id, status, featured, trending, rating, review_count, tags, created_at, updated_at)
                VALUES (:id, :name, :slug, :desc, :price, :currency, :condition, :qty, :sold, :cat_id, :seller_id, :status, :featured, :trending, :rating, :reviews, :tags, :now, :now)
                ON CONFLICT (slug) DO NOTHING
                """
            ),
            {
                "id": prod["id"],
                "name": prod["name"],
                "slug": prod["slug"],
                "desc": prod["description"],
                "price": prod["price"],
                "currency": prod["currency"],
                "condition": prod["condition"],
                "qty": prod["quantity"],
                "sold": prod["sold"],
                "cat_id": prod["category_id"],
                "seller_id": prod["seller_id"],
                "status": prod["status"],
                "featured": prod["featured"],
                "trending": prod["trending"],
                "rating": prod["rating"],
                "reviews": prod["review_count"],
                "tags": prod["tags"],
                "now": _now(),
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    # Remove seed data (in reverse order of dependencies)
    for prod in PRODUCTS:
        connection.execute(
            sa.text("DELETE FROM products WHERE id = :id"),
            {"id": prod["id"]},
        )
    connection.execute(
        sa.text("DELETE FROM categories WHERE id = ANY(:ids)"),
        {"ids": [cat["id"] for cat in CATEGORIES]},
    )
    connection.execute(
        sa.text("DELETE FROM sellers WHERE id = :id"),
        {"id": SELLER_ID},
    )
    connection.execute(
        sa.text("DELETE FROM users WHERE id IN (:admin, :seller, :customer)"),
        {
            "admin": ADMIN_ID,
            "seller": SELLER_USER_ID,
            "customer": _uuid("00000000-0000-0000-0000-000000000003"),
        },
    )
