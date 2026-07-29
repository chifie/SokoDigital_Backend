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
    responses={
        200: {"description": "Password changed successfully"},
        400: {"description": "Current password is incorrect"},
    },
)
async def change_password(
    body: PasswordChangeSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the password for the currently authenticated user.

    Requires the **current password** for verification.
    The new password must be at least 6 characters long.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"message": "Password changed successfully"}


# ── POST /auth/verify-email ──────────────────────────────────────────────────

class EmailVerifySchema(BaseModel):
    """Schema for email verification."""
    token: str = Field(..., description="Verification token received in email")
    email: EmailStr = Field(..., description="Email address to verify")


@router.post(
    "/verify-email",
    summary="Verify email address with a token",
    responses={
        200: {"description": "Email verified successfully"},
        400: {"description": "Invalid or expired verification token"},
        404: {"description": "User not found"},
    },
)
async def verify_email(
    body: EmailVerifySchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify a user's email address using the token sent during registration.

    The verification link is sent to the user's email upon registration.
    Tokens expire after 24 hours.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(User).where(
            User.email == body.email,
            User.verification_token == body.token,
            User.verification_token_expires_at > now,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Check if user exists but token is wrong/expired
        user_check = await db.execute(
            select(User).where(User.email == body.email)
        )
        user = user_check.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if user.is_verified:
            return {"message": "Email already verified", "verified": True}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token. Request a new one.",
        )

    if user.is_verified:
        return {"message": "Email already verified", "verified": True}

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires_at = None
    await db.commit()

    return {"message": "Email verified successfully", "verified": True}


# ── POST /auth/resend-verification ───────────────────────────────────────────

class ResendVerificationSchema(BaseModel):
    """Schema for resending verification email."""
    email: EmailStr


@router.post(
    "/resend-verification",
    summary="Resend the email verification link",
    responses={
        200: {"description": "Verification email resent"},
        400: {"description": "Email already verified"},
        404: {"description": "User not found"},
    },
)
async def resend_verification(
    body: ResendVerificationSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Resend the email verification link to a user's email address.

    Use this if the original verification email was lost or the token expired.
    A new token is generated, invalidating the previous one.
    """
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found with this email",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified",
        )

    # Generate new token
    verification_token = uuid.uuid4().hex
    verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

    user.verification_token = verification_token
    user.verification_token_expires_at = verification_token_expires_at
    await db.commit()

    # Send verification email
    verify_url = f"{settings.APP_URL}/verify-email?token={verification_token}&email={body.email}"
    try:
        await send_email(
            to_email=body.email,
            template_name="email_verification",
            context={"verify_url": verify_url},
        )
    except Exception:
        pass

    return {"message": "Verification email sent. Please check your inbox."}


# ── POST /auth/forgot-password ───────────────────────────────────────────────

class ForgotPasswordSchema(BaseModel):
    """Schema for requesting a password reset."""
    email: EmailStr = Field(..., description="Email address to send reset link to")


@router.post(
    "/forgot-password",
    summary="Request a password reset email",
    responses={
        200: {"description": "Reset email sent if account exists"},
    },
)
async def forgot_password(
    body: ForgotPasswordSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset email.

    If an account with the given email exists, a password reset link
    will be sent. For security, this endpoint always returns a success
    message regardless of whether the email exists (to prevent email enumeration).
    """
    result = await db.execute(
        select(User).where(User.email == body.email)
    )
    user = result.scalar_one_or_none()

    if user is not None and user.is_active:
        # Generate reset token (valid for 1 hour)
        reset_token = uuid.uuid4().hex
        reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        user.password_reset_token = reset_token
        user.password_reset_token_expires_at = reset_token_expires_at
        await db.commit()

        # Send password reset email
        reset_url = f"{settings.APP_URL}/reset-password?token={reset_token}&email={body.email}"
        try:
            await send_email(
                to_email=body.email,
                template_name="password_reset",
                context={"reset_url": reset_url},
            )
        except Exception:
            pass

    # Always return success to prevent email enumeration
    return {
        "message": "If an account with that email exists, a password reset link has been sent."
    }


# ── POST /auth/reset-password ────────────────────────────────────────────────

class ResetPasswordSchema(BaseModel):
    """Schema for resetting password with a token."""
    token: str = Field(..., description="Password reset token from email")
    email: EmailStr = Field(..., description="Email address")
    new_password: str = Field(..., min_length=6, max_length=255, description="New password")


@router.post(
    "/reset-password",
    summary="Reset password using a reset token",
    responses={
        200: {"description": "Password reset successfully"},
        400: {"description": "Invalid or expired reset token"},
    },
)
async def reset_password(
    body: ResetPasswordSchema,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset a user's password using a reset token.

    The token is sent via email through the ``/auth/forgot-password`` endpoint.
    Tokens expire after 1 hour.
    """
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(User).where(
            User.email == body.email,
            User.password_reset_token == body.token,
            User.password_reset_token_expires_at > now,
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token. Please request a new one.",
        )

    # Update password and clear reset token
    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_token_expires_at = None
    await db.commit()

    return {"message": "Password has been reset successfully."}
