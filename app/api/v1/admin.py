import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.database import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.seller import Seller
from app.models.shopping import Order, OrderItem, Review
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


# ═══════════════════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/users", response_model=list[UserResponse], summary="List all users (admin)")
async def list_users(
    role: str | None = Query(None, description="Filter by role: customer, seller, admin"),
    search: str | None = Query(None, description="Search by email or username"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.role == role)
    if search:
        stmt = stmt.where(
            (User.email.ilike(f"%{search}%")) | (User.username.ilike(f"%{search}%"))
        )
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/users/{user_id}", response_model=UserResponse, summary="Get user details (admin)")
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/users/{user_id}/role", summary="Update user role (admin)")
async def update_user_role(
    user_id: uuid.UUID,
    role: str = Query(..., pattern=r"^(customer|seller|admin)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = role
    await db.commit()
    return {"message": f"User role updated to {role}"}


@router.put("/users/{user_id}/toggle-active", summary="Toggle user active status (admin)")
async def toggle_user_active(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = not user.is_active
    await db.commit()
    return {"message": f"User {'activated' if user.is_active else 'deactivated'}"}


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCT MODERATION
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/products", summary="List all products for moderation (admin)")
async def list_all_products(
    status: str | None = Query(None, description="Filter by status"),
    seller_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    stmt = select(Product).order_by(Product.created_at.desc())
    if status:
        stmt = stmt.where(Product.status == status)
    if seller_id:
        stmt = stmt.where(Product.seller_id == seller_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/products/{product_id}/status", summary="Moderate product status (admin)")
async def moderate_product(
    product_id: uuid.UUID,
    status: str = Query(..., pattern=r"^(active|draft|archived)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product.status = status
    await db.commit()
    return {"message": f"Product status updated to {status}"}


# ═══════════════════════════════════════════════════════════════════════════
# ANALYTICS / DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", summary="Get admin dashboard stats")
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Aggregated marketplace stats for the admin dashboard."""
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_sellers = (await db.execute(select(func.count(User.id)).where(User.role == "seller"))).scalar() or 0
    total_products = (await db.execute(select(func.count(Product.id)))).scalar() or 0
    active_products = (await db.execute(select(func.count(Product.id)).where(Product.status == "active"))).scalar() or 0
    total_orders = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    total_revenue = (await db.execute(select(func.coalesce(func.sum(Order.total), 0)))).scalar() or 0.0
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    total_seller_accounts = (await db.execute(select(func.count(Seller.id)))).scalar() or 0

    return {
        "total_users": total_users,
        "total_sellers": total_sellers,
        "total_seller_accounts": total_seller_accounts,
        "total_products": total_products,
        "active_products": active_products,
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "average_order_value": round(avg_order_value, 2),
    }


@router.get("/analytics/revenue", summary="Get revenue analytics")
async def revenue_analytics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Revenue breakdown by day for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            cast(Order.created_at, Date).label("date"),
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
            func.count(Order.id).label("orders"),
        )
        .where(Order.created_at >= cutoff)
        .group_by(cast(Order.created_at, Date))
        .order_by(cast(Order.created_at, Date))
    )
    daily_sales = [
        {"date": str(row.date), "amount": float(row.revenue), "orders": row.orders}
        for row in result.all()
    ]
    return {
        "total_revenue": round(sum(d["amount"] for d in daily_sales), 2),
        "total_orders": sum(d["orders"] for d in daily_sales),
        "daily_sales": daily_sales,
    }


@router.get("/analytics/top-products", summary="Get top selling products")
async def top_products(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Top products by units sold."""
    result = await db.execute(
        select(Product)
        .where(Product.status == "active")
        .order_by(Product.sold.desc())
        .limit(limit)
    )
    return [
        {
            "product_id": str(p.id),
            "name": p.name,
            "sales": p.sold,
            "revenue": round(p.sold * (p.discount_price or p.price), 2),
        }
        for p in result.scalars().all()
    ]


@router.get("/analytics/by-category", summary="Get revenue by category")
async def revenue_by_category(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Revenue breakdown by product category."""
    result = await db.execute(
        select(
            Category.name,
            func.coalesce(func.sum(Product.sold * (Product.discount_price or Product.price)), 0).label("revenue"),
            func.sum(Product.sold).label("sales"),
        )
        .join(Category, Product.category_id == Category.id, isouter=True)
        .group_by(Category.name)
        .order_by(func.sum(Product.sold * (Product.discount_price or Product.price)).desc())
    )
    rows = result.all()
    total = sum(float(r.revenue) for r in rows) or 1
    return [
        {
            "category": r.name or "Uncategorized",
            "revenue": round(float(r.revenue), 2),
            "sales": int(r.sales),
            "percentage": round(float(r.revenue) / total * 100, 1),
        }
        for r in rows
    ]
