import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Register ────────────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=255)
    full_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)


# ── Login ───────────────────────────────────────────────────────────────────
class UserLogin(BaseModel):
    """Schema for user login — accepts email or username as identity."""
    identity: str = Field(..., description="Email or username")
    password: str = Field(..., min_length=1)


# ── Token ───────────────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    """Schema returned on successful authentication."""
    access_token: str
    token_type: str = "bearer"


# ── User response (public-facing) ───────────────────────────────────────────
class UserResponse(BaseModel):
    """Public user data returned to clients (no password)."""
    id: uuid.UUID
    email: str
    username: str
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
