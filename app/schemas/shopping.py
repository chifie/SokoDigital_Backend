import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Address ─────────────────────────────────────────────────────────────────
class AddressCreate(BaseModel):
    label: str = "Home"
    street: str = Field(..., max_length=500)
    city: str = Field(..., max_length=200)
    state: str | None = Field(None, max_length=200)
    zip_code: str | None = Field(None, max_length=20)
    country: str = "Tanzania"
    phone: str | None = Field(None, max_length=20)
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    phone: str | None = None
    is_default: bool | None = None


class AddressResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    label: str
    street: str
    city: str
    state: str | None = None
    zip_code: str | None = None
    country: str
    phone: str | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Order ───────────────────────────────────────────────────────────────────
class OrderItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1)


class CheckoutRequest(BaseModel):
    shipping_address_id: uuid.UUID
    notes: str | None = None
    items: list[OrderItemCreate] = Field(..., min_length=1)


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: int
    unit_price: float
    subtotal: float

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    total: float
    shipping_address_id: uuid.UUID | None = None
    notes: str | None = None
    status_timeline: list | None = None
    items: list[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="pending, confirmed, processing, shipped, delivered, cancelled")


# ── Review ──────────────────────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    product_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5)
    title: str | None = Field(None, max_length=255)
    comment: str | None = None


class ReviewUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    title: str | None = None
    comment: str | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    product_id: uuid.UUID
    rating: int
    title: str | None = None
    comment: str | None = None
    likes: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Wishlist ────────────────────────────────────────────────────────────────
class WishlistAddRequest(BaseModel):
    product_id: uuid.UUID


class WishlistItemResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
