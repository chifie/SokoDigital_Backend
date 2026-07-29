import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.seller import Seller
from app.models.seller_follow import SellerFollow
from app.models.user import User
from app.schemas.seller_follow import FollowResponse, FollowerResponse, FollowingStatus

router = APIRouter(prefix="/sellers", tags=["Seller Follow"])


# ── POST /sellers/{seller_id}/follow ────────────────────────────────────────
@router.post(
    "/{seller_id}/follow",
    response_model=FollowResponse,
    summary="Follow or unfollow a seller",
)
async def toggle_follow_seller(
    seller_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle follow/unfollow for a seller.

    If the user already follows the seller, the follow is removed (unfollow).
    Otherwise, a new follow relationship is created.
    """
    # Verify seller exists and is active
    result = await db.execute(
        select(Seller).where(
            Seller.id == seller_id,
            Seller.is_active == True,
        )
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller not found",
        )

    # Don't allow following yourself
    if seller.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow your own store",
        )

    # Check existing follow
    result = await db.execute(
        select(SellerFollow).where(
            SellerFollow.seller_id == seller_id,
            SellerFollow.user_id == current_user.id,
        )
    )
    existing_follow = result.scalar_one_or_none()

    if existing_follow:
        # Unfollow
        await db.delete(existing_follow)
        seller.followers = max(0, seller.followers - 1)
        await db.commit()
        return FollowResponse(
            is_following=False,
            followers_count=seller.followers,
            message="Successfully unfollowed seller",
        )
    else:
        # Follow
        follow = SellerFollow(seller_id=seller_id, user_id=current_user.id)
        db.add(follow)
        seller.followers += 1
        await db.commit()
        return FollowResponse(
            is_following=True,
            followers_count=seller.followers,
            message="Successfully followed seller",
        )


# ── GET /sellers/{seller_id}/followers ─────────────────────────────────────
@router.get(
    "/{seller_id}/followers",
    response_model=list[FollowerResponse],
    summary="List followers of a seller",
)
async def list_followers(
    seller_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List users who follow a specific seller."""
    # Verify seller exists
    result = await db.execute(
        select(Seller).where(Seller.id == seller_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller not found",
        )

    result = await db.execute(
        select(SellerFollow)
        .where(SellerFollow.seller_id == seller_id)
        .order_by(SellerFollow.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


# ── GET /sellers/{seller_id}/follow/status ─────────────────────────────────
@router.get(
    "/{seller_id}/follow/status",
    response_model=FollowingStatus,
    summary="Check if the current user follows a seller",
)
async def following_status(
    seller_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check whether the authenticated user follows a specific seller."""
    result = await db.execute(
        select(SellerFollow).where(
            SellerFollow.seller_id == seller_id,
            SellerFollow.user_id == current_user.id,
        )
    )
    return FollowingStatus(is_following=result.scalar_one_or_none() is not None)


# ── GET /sellers/following/mine ─────────────────────────────────────────────
@router.get(
    "/following/mine",
    response_model=list[FollowerResponse],
    summary="List sellers the current user follows",
)
async def my_followed_sellers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sellers that the authenticated user follows."""
    result = await db.execute(
        select(SellerFollow)
        .where(SellerFollow.user_id == current_user.id)
        .order_by(SellerFollow.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
