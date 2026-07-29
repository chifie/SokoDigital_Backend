import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.database import get_db
from app.models.shopping import Address
from app.models.user import User
from app.schemas.shopping import AddressCreate, AddressResponse, AddressUpdate

router = APIRouter(prefix="/addresses", tags=["Addresses"])


async def _get_address_or_404(db: AsyncSession, address_id: uuid.UUID, user_id: uuid.UUID) -> Address:
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == user_id)
    )
    address = result.scalar_one_or_none()
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    return address


@router.get(
    "",
    response_model=list[AddressResponse],
    summary="List all addresses for the current user",
    response_description="List of saved addresses, default first",
)
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all addresses belonging to the authenticated user.

    Results are ordered with the default address first, then by
    creation date (newest first).
    """
    result = await db.execute(
        select(Address).where(Address.user_id == current_user.id).order_by(Address.is_default.desc(), Address.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address",
    response_description="The newly created address",
)
async def create_address(
    body: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new shipping or billing address for the current user.

    If ``is_default`` is set to ``True``, any existing default address
    will be unset first.
    """
    if body.is_default:
        # Unset any existing default address
        existing_default = await db.execute(
            select(Address).where(
                Address.user_id == current_user.id,
                Address.is_default == True,
            )
        )
        old_default = existing_default.scalar_one_or_none()
        if old_default:
            old_default.is_default = False

    address = Address(**body.model_dump(), user_id=current_user.id)
    db.add(address)
    await db.commit()
    await db.refresh(address)
    return address


@router.get(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Get a single address by ID",
    responses={404: {"description": "Address not found"}},
)
async def get_address(
    address_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a specific address by its ID.

    Only returns addresses belonging to the authenticated user.
    """
    return await _get_address_or_404(db, address_id, current_user.id)


@router.put(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Update an existing address",
    response_description="The updated address",
    responses={404: {"description": "Address not found"}},
)
async def update_address(
    address_id: uuid.UUID,
    body: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update one or more fields of an existing address.

    Only fields provided in the request body will be updated.
    """
    address = await _get_address_or_404(db, address_id, current_user.id)

    if body.is_default == True:
        await db.execute(
            Address.__table__.update().where(
                Address.user_id == current_user.id,
                Address.id != address_id
            ).values(is_default=False)
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(address, field, value)

    await db.commit()
    await db.refresh(address)
    return address


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an address",
    response_description="Address deleted successfully",
    responses={404: {"description": "Address not found"}},
)
async def delete_address(
    address_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an address from the user's saved addresses."""
    address = await _get_address_or_404(db, address_id, current_user.id)
    await db.delete(address)
    await db.commit()
