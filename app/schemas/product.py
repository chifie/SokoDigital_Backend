import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Product Image ───────────────────────────────────────────────────────────
class ProductImageSchema(BaseModel):
    id: uuid.UUID | None = None
    url: str
    alt_text: str | None = None
    sort_order: int = 0

    model_config = {"from_attributes": True}


# ── Create ──────────────────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str = Field(..., max_length=500)
    slug: str = Field(..., max_length=500, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None

    price: float = Field(..., gt=0)
    discount_price: float | None = Field(None, gt=0)
    currency: str = "TZS"

    brand: str | None = Field(None, max_length=255)
    sku: str | None = Field(None, max_length=100)
    condition: str = "new"

    quantity: int = 0
    category_id: uuid.UUID | None = None

    specifications: dict | None = None
    colors: list[str] | None = None
    sizes: list[str] | None = None
    tags: list[str] | None = None
    delivery_options: dict | None = None

    images: list[ProductImageSchema] = []

    warranty: str | None = None
    return_policy: str | None = None


# ── Update ──────────────────────────────────────────────────────────────────
class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=500)
    slug: str | None = Field(
        None, max_length=500, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    description: str | None = None
    price: float | None = Field(None, gt=0)
    discount_price: float | None = Field(None, gt=0)
    currency: str | None = None
    brand: str | None = None
    sku: str | None = None
    condition: str | None = None
    quantity: int | None = None
    category_id: uuid.UUID | None = None
    specifications: dict | None = None
    colors: list[str] | None = None
    sizes: list[str] | None = None
    tags: list[str] | None = None
    delivery_options: dict | None = None
    status: str | None = None
    featured: bool | None = None
    trending: bool | None = None
    warranty: str | None = None
    return_policy: str | None = None


# ── Response ────────────────────────────────────────────────────────────────
class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    price: float
    discount_price: float | None = None
    currency: str
    brand: str | None = None
    sku: str | None = None
    condition: str
    quantity: int
    sold: int
    category_id: uuid.UUID | None = None
    seller_id: uuid.UUID
    specifications: dict | None = None
    colors: list[str] | None = None
    sizes: list[str] | None = None
    tags: list[str] | None = None
    delivery_options: dict | None = None
    status: str
    featured: bool
    trending: bool
    rating: float
    review_count: int
    warranty: str | None = None
    return_policy: str | None = None
    images: list[ProductImageSchema] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Search / Filter ─────────────────────────────────────────────────────────
class ProductSearchParams(BaseModel):
    q: str | None = Field(None, description="Full-text search query")
    category_id: uuid.UUID | None = None
    seller_id: uuid.UUID | None = None
    min_price: float | None = None
    max_price: float | None = None
    condition: str | None = None
    status: str = "active"
    featured: bool | None = None
    trending: bool | None = None
    sort_by: str | None = Field(
        None, description="created_at, price, rating, sold"
    )
    sort_order: str = "desc"
    skip: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)
