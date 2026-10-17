"""Product endpoints, and conversion between the API shape and the tables.

The API nests what the tables keep flat (npk -> four columns, frequency ->
kind and days), so conversion is written out by hand in both directions.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session, selectinload

from app.database import get_session
from app.models import Product, ProductLabelDirection
from app.schemas import (
    EveryWateringFrequency,
    IntervalFrequency,
    LabelDirection,
    Npk,
    ProductCreate,
    ProductRead,
)


def fill_product(product: Product, data: ProductCreate) -> Product:
    """Write data into product, replacing all of its label directions.

    Used for both create (a new Product) and update (an existing one).
    On update this flushes: the old directions are deleted in the open
    transaction, so the caller must commit or roll back afterwards.
    """
    # On update, delete the old directions before adding the new ones. A
    # flush otherwise inserts before it deletes, so a direction that keeps
    # its use or position would collide with the row it replaces under the
    # unique indexes. This runs before any field changes, so the flush sends
    # only the deletes; a duplicate brand and name then fails at commit,
    # where the caller turns it into 409.
    session = object_session(product)
    if session is not None and product.label_directions:
        product.label_directions.clear()
        session.flush()

    product.brand = data.brand
    product.name = data.name
    product.type = data.type
    product.notes = data.notes

    npk = data.npk
    product.npk_n = npk.n if npk else None
    product.npk_p = npk.p if npk else None
    product.npk_k = npk.k if npk else None
    product.npk_basis = npk.basis if npk else None

    product.label_directions = [
        direction_to_row(direction, position)
        for position, direction in enumerate(data.label_directions)
    ]
    return product


def direction_to_row(direction: LabelDirection, position: int) -> ProductLabelDirection:
    match direction.frequency:
        case IntervalFrequency(days=days):
            kind, frequency_days = "interval", days
        case EveryWateringFrequency():
            kind, frequency_days = "every_watering", None
    return ProductLabelDirection(
        position=position,
        amount=direction.amount,
        amount_unit=direction.amount_unit,
        water_volume=direction.water_volume,
        water_unit=direction.water_unit,
        frequency_kind=kind,
        frequency_days=frequency_days,
        use=direction.use,
    )


def product_to_read(product: Product) -> ProductRead:
    npk = None
    if product.npk_n is not None:
        npk = Npk(
            n=product.npk_n,
            p=product.npk_p,
            k=product.npk_k,
            basis=product.npk_basis,
        )
    return ProductRead(
        id=product.id,
        created_at=product.created_at,
        brand=product.brand,
        name=product.name,
        type=product.type,
        npk=npk,
        label_directions=[row_to_direction(row) for row in product.label_directions],
        notes=product.notes,
    )


def row_to_direction(row: ProductLabelDirection) -> LabelDirection:
    if row.frequency_kind == "interval":
        frequency = IntervalFrequency(kind="interval", days=row.frequency_days)
    else:
        frequency = EveryWateringFrequency(kind="every_watering")
    return LabelDirection(
        amount=row.amount,
        amount_unit=row.amount_unit,
        water_volume=row.water_volume,
        water_unit=row.water_unit,
        frequency=frequency,
        use=row.use,
    )


router = APIRouter(prefix="/products", tags=["products"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, session: SessionDep) -> ProductRead:
    product = fill_product(Product(), data)
    session.add(product)
    commit_or_conflict(session)
    return product_to_read(product)


@router.get("")
def list_products(session: SessionDep) -> list[ProductRead]:
    products = session.scalars(
        select(Product)
        # Load all directions in one extra query, not one query per product.
        .options(selectinload(Product.label_directions))
        .order_by(func.lower(Product.brand), func.lower(Product.name))
    )
    return [product_to_read(product) for product in products]


@router.get("/{product_id}")
def get_product(product_id: int, session: SessionDep) -> ProductRead:
    return product_to_read(get_or_404(session, product_id))


@router.put("/{product_id}")
def replace_product(product_id: int, data: ProductCreate, session: SessionDep) -> ProductRead:
    """Replace every field and all label directions; id and created_at stay."""
    product = fill_product(get_or_404(session, product_id), data)
    commit_or_conflict(session)
    return product_to_read(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, session: SessionDep) -> None:
    # Its label directions go with it (ON DELETE CASCADE).
    session.delete(get_or_404(session, product_id))
    session.commit()


def get_or_404(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found")
    return product


def commit_or_conflict(session: Session) -> None:
    """Commit, turning a duplicate brand and name into 409 Conflict.

    The unique index decides, instead of a lookup before the insert: two
    requests could both look, find nothing, and both insert. Any other
    IntegrityError means Pydantic let bad data through, which is a bug, so
    it is re-raised and becomes a 500. No rollback is needed here: the
    request's session is closed when the request ends, which rolls back.
    """
    try:
        session.commit()
    except IntegrityError as error:
        if "uq_products_brand_name" in str(error.orig):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "A product with this brand and name already exists"
            ) from error
        raise
