import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Coupon ──────────────────────────────────────────────────────────────────
class CouponCreate(BaseModel):
    code: str = Field(..., max_length=50)
    type: str = Field(..., pattern=r"^(percentage|fixed)$")
    value: float = Field(..., gt=0)
    min_purchase: float = 0.0
    max_uses: int = 0
    expires_at: datetime | None = None
    applicable_categories: list[str] | None = None


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    type: str
    value: float
    min_purchase: float
    max_uses: int
    current_uses: int
    expires_at: datetime | None = None
    is_active: bool
    applicable_categories: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CouponValidateRequest(BaseModel):
    code: str
    cart_total: float = 0.0


class CouponValidateResponse(BaseModel):
    valid: bool
    message: str | None = None
    coupon: CouponResponse | None = None
    discount: float | None = None


# ── FlashSale ───────────────────────────────────────────────────────────────
class FlashSaleCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    discount: int = Field(..., ge=1, le=100)
    start_time: datetime
    end_time: datetime
    product_ids: list[str] | None = None


class FlashSaleResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    discount: int
    start_time: datetime
    end_time: datetime
    is_active: bool
    product_ids: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Banner ──────────────────────────────────────────────────────────────────
class BannerCreate(BaseModel):
    title: str = Field(..., max_length=255)
    subtitle: str | None = None
    description: str | None = None
    cta: str | None = None
    link: str | None = None
    desktop_image: str | None = None
    mobile_image: str | None = None
    badge: str | None = None
    discount: int | None = None
    countdown_to: datetime | None = None
    type: str = "hero"
    priority: int = 0
    bg_color: str | None = None
    text_color: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class BannerResponse(BaseModel):
    id: uuid.UUID
    title: str
    subtitle: str | None = None
    description: str | None = None
    cta: str | None = None
    link: str | None = None
    desktop_image: str | None = None
    mobile_image: str | None = None
    badge: str | None = None
    discount: int | None = None
    countdown_to: datetime | None = None
    type: str
    priority: int
    bg_color: str | None = None
    text_color: str | None = None
    is_active: bool
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Notification ────────────────────────────────────────────────────────────
class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    message: str | None = None
    read: bool
    link: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationUnreadCount(BaseModel):
    count: int
