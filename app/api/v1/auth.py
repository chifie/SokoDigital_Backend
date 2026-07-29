import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_optional_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.email import send_email

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── POST /auth/register ─────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        201: {"description": "User created successfully"},
        409: {"description": "Email or username already exists"},
    },
)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    """
    Create a new user account.

    A verification email will be sent to the provided email address.
    The user must verify their email before accessing certain features.

    The ``identity`` (email or username) must not already exist in the system.
    """
    # Check email
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Check username
    existing = await db.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    # Generate verification token
    verification_token = uuid.uuid4().hex
    verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        phone=body.phone,
        verification_token=verification_token,
        verification_token_expires_at=verification_token_expires_at,
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email (fire-and-forget)
    verify_url = f"{settings.APP_URL}/verify-email?token={verification_token}&email={body.email}"
    try:
        await send_email(
            to_email=body.email,
            template_name="email_verification",
            context={"verify_url": verify_url},
        )
    except Exception:
        pass  # Don't block registration if email fails

    return user


# ── POST /auth/login ────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT access token",
    responses={
        200: {"description": "Login successful, returns JWT token"},
        401: {"description": "Invalid credentials or account deactivated"},
    },
)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Authenticate with email/username + password and get an access token.

    The ``identity`` field accepts either an **email** or a **username**.
    Returns a JWT ``access_token`` that should be sent in the ``Authorization``
    header as ``Bearer <token>`` for authenticated requests.
    """
    # Find user by email or username
    result = await db.execute(
        select(User).where(
            (User.email == body.identity) | (User.username == body.identity)
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


# ── Schemas for profile update & password change ────────────────────────────

class UserUpdateSchema(BaseModel):
    """Schema for updating user profile (all fields optional)."""
    full_name: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    avatar_url: str | None = None


class PasswordChangeSchema(BaseModel):
    """Schema for changing password."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=255)


# ── GET /auth/me ────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user's profile",
)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the profile of the currently authenticated user."""
    return current_user


# ── PUT /auth/me ────────────────────────────────────────────────────────────
@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update the authenticated user's profile",
)
async def update_me(
    body: UserUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the profile of the currently authenticated user.

    Only the provided fields will be updated.
    """
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    await db.commit()
    await db.refresh(current_user)
    return current_user


# ── PUT /auth/change-password ───────────────────────────────────────────────
@router.put(
    "/change-password",
    summary="Change the authenticated user's password",
)
async def change_password(
    body: PasswordChangeSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the password for the currently authenticated user.

    Requires the current password for verification.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"message": "Password changed successfully"}
