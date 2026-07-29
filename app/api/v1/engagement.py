import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.engagement import Banner, Coupon, FlashSale, Notification
from app.models.user import User

from app.schemas.engagement import (
    BannerCreate,
    BannerResponse,
    BannerUpdate,
    CouponCreate,
    CouponResponse,
    CouponUpdate,
    CouponValidateRequest,
    CouponValidateResponse,
    FlashSaleCreate,
    FlashSaleResponse,
    FlashSaleUpdate,
    NotificationResponse,
    NotificationUnreadCount,
)

# ═══════════════════════════════════════════════════════════════════════════
# COUPONS
# ═══════════════════════════════════════════════════════════════════════════
coupon_router = APIRouter(prefix="/coupons", tags=["Coupons"])


@coupon_router.post("/validate", response_model=CouponValidateResponse, summary="Validate a coupon code")
async def validate_coupon(
    body: CouponValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate a coupon code and calculate the discount for a given cart total."""
    result = await db.execute(
        select(Coupon).where(Coupon.code == body.code)
    )
    coupon = result.scalar_one_or_none()

    if coupon is None:
        return CouponValidateResponse(valid=False, message="Coupon not found")

    if not coupon.is_active:
        return CouponValidateResponse(valid=False, message="Coupon is inactive")

    if coupon.max_uses > 0 and coupon.current_uses >= coupon.max_uses:
        return CouponValidateResponse(valid=False, message="Coupon has reached maximum uses")

    if coupon.expires_at and coupon.expires_at < datetime.now(timezone.utc):
        return CouponValidateResponse(valid=False, message="Coupon has expired")

    if body.cart_total < coupon.min_purchase:
        return CouponValidateResponse(
            valid=False,
            message=f"Minimum purchase of {coupon.min_purchase:,.0f} required",
        )

    discount = coupon.value if coupon.type == "fixed" else (body.cart_total * coupon.value / 100)

    # Increment usage count
    coupon.current_uses += 1
    await db.commit()

    return CouponValidateResponse(
        valid=True,
        message="Coupon applied successfully",
        coupon=CouponResponse.model_validate(coupon),
        discount=discount,
    )


@coupon_router.get("", response_model=list[CouponResponse], summary="List all coupons (admin)")
async def list_coupons(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Coupon).order_by(Coupon.code))
    return result.scalars().all()


@coupon_router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED, summary="Create a coupon (admin)")
async def create_coupon(
    body: CouponCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    existing = await db.execute(select(Coupon).where(Coupon.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coupon code already exists")

    coupon = Coupon(**body.model_dump())
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return coupon


@coupon_router.put("/{coupon_id}", response_model=CouponResponse, summary="Update a coupon (admin)")
async def update_coupon(
    coupon_id: uuid.UUID,
    body: CouponUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

    if body.code is not None and body.code != coupon.code:
        existing = await db.execute(select(Coupon).where(Coupon.code == body.code))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coupon code already exists")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(coupon, field, value)

    await db.commit()
    await db.refresh(coupon)
    return coupon


@coupon_router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a coupon (admin)")
async def delete_coupon(
    coupon_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

    await db.delete(coupon)
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# FLASH SALES
# ═══════════════════════════════════════════════════════════════════════════
flash_sale_router = APIRouter(prefix="/flash-sales", tags=["Flash Sales"])


@flash_sale_router.get("", response_model=list[FlashSaleResponse], summary="List active flash sales")
async def list_flash_sales(
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(FlashSale)
        .where(
            FlashSale.is_active == True,
            FlashSale.start_time <= now,
            FlashSale.end_time >= now,
        )
        .order_by(FlashSale.created_at.desc())
    )
    return result.scalars().all()


@flash_sale_router.post("", response_model=FlashSaleResponse, status_code=status.HTTP_201_CREATED, summary="Create a flash sale (admin)")
async def create_flash_sale(
    body: FlashSaleCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    flash_sale = FlashSale(**body.model_dump())
    db.add(flash_sale)
    await db.commit()
    await db.refresh(flash_sale)
    return flash_sale


@flash_sale_router.put("/{flash_sale_id}", response_model=FlashSaleResponse, summary="Update a flash sale (admin)")
async def update_flash_sale(
    flash_sale_id: uuid.UUID,
    body: FlashSaleUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(FlashSale).where(FlashSale.id == flash_sale_id))
    flash_sale = result.scalar_one_or_none()
    if flash_sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flash sale not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(flash_sale, field, value)

    await db.commit()
    await db.refresh(flash_sale)
    return flash_sale


@flash_sale_router.delete("/{flash_sale_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a flash sale (admin)")
async def delete_flash_sale(
    flash_sale_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(FlashSale).where(FlashSale.id == flash_sale_id))
    flash_sale = result.scalar_one_or_none()
    if flash_sale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flash sale not found")

    await db.delete(flash_sale)
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# BANNERS
# ═══════════════════════════════════════════════════════════════════════════
banner_router = APIRouter(prefix="/banners", tags=["Banners"])


@banner_router.get("", response_model=list[BannerResponse], summary="List active banners")
async def list_active_banners(
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Banner)
        .where(
            Banner.is_active == True,
            (Banner.start_date <= now) | (Banner.start_date.is_(None)),
            (Banner.end_date >= now) | (Banner.end_date.is_(None)),
        )
        .order_by(Banner.priority.desc(), Banner.created_at.desc())
    )
    return result.scalars().all()


@banner_router.post("", response_model=BannerResponse, status_code=status.HTTP_201_CREATED, summary="Create a banner (admin)")
async def create_banner(
    body: BannerCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    banner = Banner(**body.model_dump())
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return banner


@banner_router.put("/{banner_id}", response_model=BannerResponse, summary="Update a banner (admin)")
async def update_banner(
    banner_id: uuid.UUID,
    body: BannerUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if banner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(banner, field, value)

    await db.commit()
    await db.refresh(banner)
    return banner


@banner_router.delete("/{banner_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a banner (admin)")
async def delete_banner(
    banner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if banner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")

    await db.delete(banner)
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════
notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])


@notification_router.get("", response_model=list[NotificationResponse], summary="List my notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    if unread_only:
        stmt = stmt.where(Notification.read == False)
    result = await db.execute(stmt)
    return result.scalars().all()


@notification_router.get("/unread-count", response_model=NotificationUnreadCount, summary="Get unread notification count")
async def unread_notification_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.read == False,
        )
    )
    count = result.scalar() or 0
    return NotificationUnreadCount(count=count)


@notification_router.put("/{notification_id}/read", response_model=NotificationResponse, summary="Mark notification as read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.read = True
    await db.commit()
    await db.refresh(notification)
    return notification


@notification_router.put("/read-all", summary="Mark all notifications as read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.read == False,
        )
    )
    for notification in result.scalars().all():
        notification.read = True
    await db.commit()
    return {"message": "All notifications marked as read"}
