import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Base ────────────────────────────────────────────────────────────────────
class CategoryBase(BaseModel):
    name: str = Field(..., max_length=200)
    slug: str = Field(..., max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    image: str | None = None
    icon: str | None = Field(None, max_length=100)
    parent_id: uuid.UUID | None = None
    sort_order: int = 0
    is_active: bool = True


# ── Create ──────────────────────────────────────────────────────────────────
class CategoryCreate(CategoryBase):
    pass


# ── Update ──────────────────────────────────────────────────────────────────
class CategoryUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    slug: str | None = Field(None, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    image: str | None = None
    icon: str | None = Field(None, max_length=100)
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# ── Response ────────────────────────────────────────────────────────────────
class CategoryResponse(CategoryBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Category tree (includes children) ───────────────────────────────────────
class CategoryTreeNode(CategoryResponse):
    children: list["CategoryTreeNode"] = []

    model_config = {"from_attributes": True}
