import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.seller import Seller
from app.models.user import User
from app.schemas.seller import (
    SellerDashboard,
    SellerOnboard,
    SellerResponse,
    SellerUpdate,
)

router = APIRouter(prefix="/sellers", tags=["Sellers"])


# ── Helper ──────────────────────────────────────────────────────────────────
async def _get_seller_by_user_or_404(
    db: AsyncSession, user_id: uuid.UUID
) -> Seller:
    """Fetch a seller profile by user ID or raise 404."""
    result = await db.execute(
        select(Seller).where(Seller.user_id == user_id)
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not registered as a seller. Use /sellers/onboard first.",
        )
    return seller


# ── POST /sellers/onboard ───────────────────────────────────────────────────
@router.post(
    "/onboard",
    response_model=SellerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register as a seller (onboarding)",
)
async def onboard_seller(
    body: SellerOnboard,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register the authenticated user as a seller.

    - The user must not already have a seller profile.
    - The ``store_slug`` must be unique.
    - The user's role is automatically upgraded to ``seller``.
    """
    # Check if already a seller
    existing = await db.execute(
        select(Seller).where(Seller.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already registered as a seller",
        )

    # Check store_slug uniqueness
    slug_exists = await db.execute(
        select(Seller).where(Seller.store_slug == body.store_slug)
    )
    if slug_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This store slug is already taken",
        )

    # Create seller profile
    seller = Seller(
        user_id=current_user.id,
        store_name=body.store_name,
        store_slug=body.store_slug,
        description=body.description,
        logo=body.logo,
        banner=body.banner,
        location=body.location,
        response_time=body.response_time,
    )
    db.add(seller)

    # Upgrade user role to seller
    current_user.role = "seller"

    await db.commit()
    await db.refresh(seller)
    return seller


# ── GET /sellers/me ─────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=SellerResponse,
    summary="Get the authenticated user's seller profile",
)
async def get_my_seller_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the seller profile of the currently authenticated user."""
    return await _get_seller_by_user_or_404(db, current_user.id)


# ── PUT /sellers/me ─────────────────────────────────────────────────────────
@router.put(
    "/me",
    response_model=SellerResponse,
    summary="Update the authenticated user's seller profile",
)
async def update_my_seller_profile(
    body: SellerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the seller profile of the currently authenticated user."""
    seller = await _get_seller_by_user_or_404(db, current_user.id)

    # Check store_slug uniqueness if changing
    if body.store_slug is not None and body.store_slug != seller.store_slug:
        slug_exists = await db.execute(
            select(Seller).where(Seller.store_slug == body.store_slug)
        )
        if slug_exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This store slug is already taken",
            )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(seller, field, value)

    await db.commit()
    await db.refresh(seller)
    return seller


# ── GET /sellers/dashboard ──────────────────────────────────────────────────
@router.get(
    "/dashboard",
    response_model=SellerDashboard,
    summary="Get seller dashboard stats",
)
async def get_seller_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregated stats for the authenticated seller's dashboard."""
    seller = await _get_seller_by_user_or_404(db, current_user.id)
    return SellerDashboard(
        total_products=seller.total_products,
        total_sales=seller.total_sales,
        followers=seller.followers,
        rating=seller.rating,
        response_rate=seller.response_rate,
    )


# ── GET /sellers/{store_slug} (public) ──────────────────────────────────────
@router.get(
    "/{store_slug}",
    response_model=SellerResponse,
    summary="Get a public seller profile by store slug",
)
async def get_seller_by_slug(
    store_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a seller's public profile by their store URL slug."""
    result = await db.execute(
        select(Seller).where(
            Seller.store_slug == store_slug,
            Seller.is_active == True,
        )
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller not found",
        )
    return seller
