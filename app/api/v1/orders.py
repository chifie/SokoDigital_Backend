import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.product import Product
from app.models.seller import Seller
from app.models.shopping import Address, Order, OrderItem
from app.models.user import User
from app.schemas.common import Page
from app.schemas.shopping import (
    CheckoutRequest,
    OrderResponse,
    OrderStatusUpdate,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


async def _get_order_or_404(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> Order:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


# ── POST /orders/checkout ──────────────────────────────────────────────────
@router.post("/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, summary="Checkout and create an order")
async def checkout(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify shipping address belongs to user
    address = await db.execute(
        select(Address).where(Address.id == body.shipping_address_id, Address.user_id == current_user.id)
    )
    if address.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipping address not found")

    items_data = []
    total = 0.0

    for item_in in body.items:
        product = await db.execute(select(Product).where(Product.id == item_in.product_id, Product.status == "active"))
        product = product.scalar_one_or_none()
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {item_in.product_id} not found or inactive")

        if product.quantity < item_in.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient stock for {product.name}")

        unit_price = product.discount_price if product.discount_price is not None else product.price
        subtotal = unit_price * item_in.quantity
        total += subtotal

        items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "quantity": item_in.quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
        })

        # Decrement stock, increment sold
        product.quantity -= item_in.quantity
        product.sold += item_in.quantity

    # Create order
    order = Order(
        user_id=current_user.id,
        total=total,
        shipping_address_id=body.shipping_address_id,
        notes=body.notes,
        status="pending",
        status_timeline=[{"status": "pending", "at": datetime.now(timezone.utc).isoformat()}],
    )
    db.add(order)
    await db.flush()

    for data in items_data:
        item = OrderItem(order_id=order.id, **data)
        db.add(item)

    await db.commit()
    await db.refresh(order)
    return order


# ── GET /orders ────────────────────────────────────────────────────────────
@router.get("", response_model=list[OrderResponse], summary="List the current user's orders")
async def list_orders(
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    result = await db.execute(stmt)
    return result.scalars().unique().all()


# ── GET /orders/{order_id} ─────────────────────────────────────────────────
@router.get("/{order_id}", response_model=OrderResponse, summary="Get order details with timeline")
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _get_order_or_404(db, order_id, current_user.id)


# ── PUT /orders/{order_id}/status (seller/admin only) ──────────────────────
@router.put("/{order_id}/status", response_model=OrderResponse, summary="Update order status (seller/admin)")
async def update_order_status(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = order.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Check permission: admin or the seller who owns the products in the order
    if current_user.role != "admin":
        seller = await db.execute(select(Seller).where(Seller.user_id == current_user.id))
        seller = seller.scalar_one_or_none()
        if seller is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins or sellers can update order status")

        # Check if any items belong to this seller
        product_ids = [item.product_id for item in order.items]
        products = await db.execute(select(Product).where(Product.id.in_(product_ids)))
        seller_product_ids = {p.id for p in products.scalars().all() if p.seller_id == seller.id}
        if not seller_product_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No products in this order belong to you")

    # Update status and timeline
    old_status = order.status
    order.status = body.status
    timeline = order.status_timeline or []
    timeline.append({"status": body.status, "at": datetime.now(timezone.utc).isoformat(), "from": old_status})
    order.status_timeline = timeline

    await db.commit()
    await db.refresh(order)
    return order
