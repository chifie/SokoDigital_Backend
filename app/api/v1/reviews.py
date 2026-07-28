import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.product import Product
from app.models.shopping import Review
from app.models.user import User
from app.schemas.shopping import ReviewCreate, ReviewResponse, ReviewUpdate

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/product/{product_id}", response_model=list[ReviewResponse], summary="Get reviews for a product")
async def list_product_reviews(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED, summary="Create a review")
async def create_review(
    body: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check product exists
    product = await db.execute(select(Product).where(Product.id == body.product_id))
    product = product.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Check existing review
    existing = await db.execute(
        select(Review).where(Review.user_id == current_user.id, Review.product_id == body.product_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already reviewed this product")

    review = Review(user_id=current_user.id, **body.model_dump())
    db.add(review)

    # Update product rating
    stats = await db.execute(
        select(func.avg(Review.rating), func.count(Review.id))
        .where(Review.product_id == body.product_id)
    )
    avg, count = stats.one()
    product.rating = round(float(avg), 1) if avg else 0.0
    product.review_count = count

    await db.commit()
    await db.refresh(review)
    return review


@router.put("/{review_id}", response_model=ReviewResponse, summary="Update your review")
async def update_review(
    review_id: uuid.UUID,
    body: ReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Review).where(Review.id == review_id, Review.user_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(review, field, value)

    # Recalculate product rating
    product = await db.execute(select(Product).where(Product.id == review.product_id))
    product = product.scalar_one_or_none()
    if product:
        stats = await db.execute(
            select(func.avg(Review.rating), func.count(Review.id))
            .where(Review.product_id == review.product_id)
        )
        avg, count = stats.one()
        product.rating = round(float(avg), 1) if avg else 0.0

    await db.commit()
    await db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete your review")
async def delete_review(
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Review).where(Review.id == review_id, Review.user_id == current_user.id)
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    product = await db.execute(select(Product).where(Product.id == review.product_id))
    product = product.scalar_one_or_none()

    await db.delete(review)
    if product:
        stats = await db.execute(
            select(func.avg(Review.rating), func.count(Review.id))
            .where(Review.product_id == review.product_id)
        )
        avg, count = stats.one()
        product.rating = round(float(avg), 1) if avg else 0.0
        product.review_count = count

    await db.commit()
