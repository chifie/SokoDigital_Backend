import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryTreeNode,
    CategoryUpdate,
)


# ── Default categories matching the frontend constants ───────────────────────
SEED_CATEGORIES: list[dict] = [
    {
        "name": "Phones & Tablets",
        "slug": "phones-tablets",
        "icon": "Smartphone",
        "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800&q=100&fm=webp&fit=crop",
        "sort_order": 1,
        "children": [
            {"name": "Smartphones", "slug": "smartphones", "sort_order": 1},
            {"name": "Tablets", "slug": "tablets", "sort_order": 2},
            {"name": "Accessories", "slug": "phone-accessories", "sort_order": 3},
        ],
    },
    {
        "name": "Computers",
        "slug": "computers",
        "icon": "Monitor",
        "image": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=800&q=100&fm=webp&fit=crop",
        "sort_order": 2,
        "children": [
            {"name": "Laptops", "slug": "laptops", "sort_order": 1},
            {"name": "Desktops", "slug": "desktops", "sort_order": 2},
            {"name": "Computer Parts", "slug": "computer-parts", "sort_order": 3},
        ],
    },
    {"name": "Electronics", "slug": "electronics", "icon": "Zap", "image": "https://images.unsplash.com/photo-1468495244123-6c6c332eeece?w=800&q=100&fm=webp&fit=crop", "sort_order": 3},
    {"name": "Fashion", "slug": "fashion", "icon": "Shirt", "image": "https://images.unsplash.com/photo-1445205170230-053b83016050?w=800&q=100&fm=webp&fit=crop", "sort_order": 4},
    {"name": "Shoes", "slug": "shoes", "icon": "Footprints", "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=800&q=100&fm=webp&fit=crop", "sort_order": 5},
    {"name": "Beauty", "slug": "beauty", "icon": "Sparkles", "image": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=800&q=100&fm=webp&fit=crop", "sort_order": 6},
    {"name": "Groceries", "slug": "groceries", "icon": "Apple", "image": "https://images.unsplash.com/photo-1542838132-92c53300491e?w=800&q=100&fm=webp&fit=crop", "sort_order": 7},
    {"name": "Furniture", "slug": "furniture", "icon": "Armchair", "image": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800&q=100&fm=webp&fit=crop", "sort_order": 8},
    {"name": "Home & Kitchen", "slug": "home-kitchen", "icon": "Home", "image": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=800&q=100&fm=webp&fit=crop", "sort_order": 9},
    {"name": "Gaming", "slug": "gaming", "icon": "Gamepad2", "image": "https://images.unsplash.com/photo-1593305841991-05c297ba4575?w=800&q=100&fm=webp&fit=crop", "sort_order": 10},
    {"name": "Automotive", "slug": "automotive", "icon": "Car", "image": "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=800&q=100&fm=webp&fit=crop", "sort_order": 11},
    {"name": "Sports", "slug": "sports", "icon": "Trophy", "image": "https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=800&q=100&fm=webp&fit=crop", "sort_order": 12},
    {"name": "Baby Products", "slug": "baby-products", "icon": "Baby", "image": "https://images.unsplash.com/photo-1519689680058-324335c77eba?w=800&q=100&fm=webp&fit=crop", "sort_order": 13},
    {"name": "Books", "slug": "books", "icon": "BookOpen", "image": "https://images.unsplash.com/photo-1495446815901-a7297e633e8d?w=800&q=100&fm=webp&fit=crop", "sort_order": 14},
    {"name": "Health", "slug": "health", "icon": "Heart", "image": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800&q=100&fm=webp&fit=crop", "sort_order": 15},
]

router = APIRouter(prefix="/categories", tags=["Categories"])


# ── Helper ──────────────────────────────────────────────────────────────────
async def _get_category_or_404(
    db: AsyncSession, category_id: uuid.UUID
) -> Category:
    """Fetch a category by ID or raise 404."""
    result = await db.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


# ── GET /categories (flat list) ─────────────────────────────────────────────
@router.get(
    "",
    response_model=list[CategoryResponse],
    summary="List all categories (flat list)",
    response_description="Flat list of categories sorted by sort_order and name",
)
async def list_categories(
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = Query(False, description="Include inactive categories"),
):
    """
    Return all categories as a flat list.

    Parent categories and subcategories are returned in a single-level array.
    Use ``/categories/tree`` for a hierarchical navigation view.
    Pass ``?include_inactive=true`` to include disabled categories.
    """
    stmt = select(Category).order_by(Category.sort_order, Category.name)
    if not include_inactive:
        stmt = stmt.where(Category.is_active == True)

    result = await db.execute(stmt)
    categories = result.scalars().all()

    # Only return top-level categories (no parent) — their children are loaded
    return [c for c in categories if c.parent_id is None]


# ── GET /categories/tree (nested tree) ──────────────────────────────────────
@router.get(
    "/tree",
    response_model=list[CategoryTreeNode],
    summary="List categories as a nested tree",
    response_description="Hierarchical category tree ideal for navigation menus",
)
async def list_category_tree(
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = Query(False, description="Include inactive categories"),
):
    """
    Return all top-level categories with their subcategories nested inside
    the ``children`` array.

    This is the ideal endpoint for building navigation menus and category
    dropdowns on the frontend.
    """
    stmt = (
        select(Category)
        .options(selectinload(Category.children))
        .order_by(Category.sort_order, Category.name)
    )
    if not include_inactive:
        stmt = stmt.where(Category.is_active == True)

    result = await db.execute(stmt)
    categories = result.scalars().unique().all()

    # Only return top-level categories (no parent) — their children are loaded
    return [c for c in categories if c.parent_id is None]


# ── GET /categories/{slug} ──────────────────────────────────────────────────
@router.get(
    "/{slug}",
    response_model=CategoryTreeNode,
    summary="Get a single category by slug (with children)",
)
async def get_category_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single category by its URL slug, including its subcategories."""
    result = await db.execute(
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.slug == slug)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


# ── POST /categories (admin only) ───────────────────────────────────────────
@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category (admin only)",
)
async def create_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Create a new category. Requires authentication.

    The slug must be unique.
    """
    # Check slug uniqueness
    existing = await db.execute(
        select(Category).where(Category.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this slug already exists",
        )

    # Validate parent_id if provided
    if body.parent_id is not None:
        parent = await db.execute(
            select(Category).where(Category.id == body.parent_id)
        )
        if parent.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found",
            )

    category = Category(**body.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


# ── PUT /categories/{category_id} (admin only) ──────────────────────────────
@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update a category (admin only)",
)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Update an existing category. Requires authentication."""
    category = await _get_category_or_404(db, category_id)

    # Check slug uniqueness if slug is being changed
    if body.slug is not None and body.slug != category.slug:
        existing = await db.execute(
            select(Category).where(Category.slug == body.slug)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this slug already exists",
            )

    # Update only provided fields
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category


# ── POST /categories/seed (admin only) ──────────────────────────────────────
@router.post(
    "/seed",
    status_code=status.HTTP_201_CREATED,
    summary="Seed default categories from frontend constants (admin only)",
)
async def seed_categories(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Insert the default categories matching the frontend constants.
    Skips any categories whose slug already exists. Returns a summary
    of how many categories and subcategories were created.
    """
    created_parents = 0
    created_children = 0

    for parent_data in SEED_CATEGORIES:
        children_data = parent_data.get("children", [])

        # Skip if slug exists
        existing = await db.execute(
            select(Category).where(Category.slug == parent_data["slug"])
        )
        if existing.scalar_one_or_none():
            continue

        parent = Category(**parent_data)
        db.add(parent)
        await db.flush()
        created_parents += 1

        for child_data in children_data:
            existing = await db.execute(
                select(Category).where(Category.slug == child_data["slug"])
            )
            if existing.scalar_one_or_none():
                continue

            child = Category(**child_data, parent_id=parent.id)
            db.add(child)
            created_children += 1

    await db.commit()
    return {
        "created_categories": created_parents,
        "created_subcategories": created_children,
    }


# ── DELETE /categories/{category_id} (admin only) ───────────────────────────
@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (admin only)",
)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    """Delete a category. Its subcategories will have ``parent_id`` set to NULL
    (``ON DELETE SET NULL``). Requires authentication.
    """
    category = await _get_category_or_404(db, category_id)
    await db.delete(category)
    await db.commit()
