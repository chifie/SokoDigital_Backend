import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Onboard / Create ────────────────────────────────────────────────────────
class SellerOnboard(BaseModel):
    """Schema for a user to register as a seller (onboarding)."""
    store_name: str = Field(..., max_length=255)
    store_slug: str = Field(
        ..., max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    description: str | None = None
    logo: str | None = None
    banner: str | None = None
    location: str | None = Field(None, max_length=255)
    response_time: str | None = Field("within 1 hour", max_length=100)


# ── Update ──────────────────────────────────────────────────────────────────
class SellerUpdate(BaseModel):
    store_name: str | None = Field(None, max_length=255)
    store_slug: str | None = Field(
        None, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    description: str | None = None
    logo: str | None = None
    banner: str | None = None
    location: str | None = Field(None, max_length=255)
    response_time: str | None = Field(None, max_length=100)


# ── Response (public profile) ───────────────────────────────────────────────
class SellerResponse(BaseModel):
    """Public seller profile returned to clients."""
    id: uuid.UUID
    user_id: uuid.UUID
    store_name: str
    store_slug: str
    description: str | None = None
    logo: str | None = None
    banner: str | None = None
    location: str | None = None
    rating: float
    total_sales: int
    total_products: int
    followers: int
    response_rate: int
    response_time: str | None = None
    is_verified: bool
    badges: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard stats ─────────────────────────────────────────────────────────
class SellerDashboard(BaseModel):
    """Aggregated stats for the seller's dashboard."""
    total_products: int
    total_sales: int
    followers: int
    rating: float
    response_rate: int
