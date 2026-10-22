"""Product endpoints, and conversion between the API shape and the tables.

The API nests what the tables keep flat (npk -> four columns, frequency ->
kind and days), so conversion is written out by hand in both directions.
"""

from fastapi import APIRouter, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import object_session, selectinload

from app.core.api import SessionDep, commit_or_conflict, get_or_404
from app.products.models import Product, ProductLabelDirection
from app.products.schemas import (
    AsNeededFrequency,
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
    On update the old directions are deleted in the open transaction, so the
    caller must commit or roll back afterwards.
    """
    session = object_session(product)
    if session is None:  # a new product: nothing saved, nothing to delete
        return write_product(product, data)

    # On update, delete the old directions with one DELETE, which runs right
    # away; new ones added on top of them would collide with rows that keep
    # their use or position (a flush inserts before it deletes).
    # no_autoflush: nothing else is sent before commit. Otherwise the DELETE,
    # or loading the old list to replace it, would first send the field
    # changes, and a duplicate name would fail here instead of at commit,
    # where the caller turns it into 409.
    with session.no_autoflush:
        session.execute(
            delete(ProductLabelDirection).where(ProductLabelDirection.product_id == product.id)
        )
        return write_product(product, data)


def write_product(product: Product, data: ProductCreate) -> Product:
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
        case AsNeededFrequency():
            kind, frequency_days = "as_needed", None
    return ProductLabelDirection(
        position=position,
        application=direction.application,
        amount=direction.amount,
        amount_unit=direction.amount_unit,
        water_volume=direction.water_volume,
        water_unit=direction.water_unit,
        frequency_kind=kind,
        frequency_days=frequency_days,
        use=direction.use,
        details=direction.details,
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
    match row.frequency_kind:
        case "interval":
            frequency = IntervalFrequency(kind="interval", days=row.frequency_days)
        case "every_watering":
            frequency = EveryWateringFrequency(kind="every_watering")
        case "as_needed":
            frequency = AsNeededFrequency(kind="as_needed")
    return LabelDirection(
        application=row.application,
        amount=row.amount,
        amount_unit=row.amount_unit,
        water_volume=row.water_volume,
        water_unit=row.water_unit,
        frequency=frequency,
        use=row.use,
        details=row.details,
    )


router = APIRouter(prefix="/products", tags=["products"])

DUPLICATE = ("uq_products_brand_name", "A product with this brand and name already exists")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, session: SessionDep) -> ProductRead:
    product = fill_product(Product(), data)
    session.add(product)
    commit_or_conflict(session, *DUPLICATE)
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
    return product_to_read(get_or_404(session, Product, product_id, "Product"))


@router.put("/{product_id}")
def replace_product(product_id: int, data: ProductCreate, session: SessionDep) -> ProductRead:
    """Replace every field and all label directions; id and created_at stay."""
    product = fill_product(get_or_404(session, Product, product_id, "Product"), data)
    commit_or_conflict(session, *DUPLICATE)
    return product_to_read(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, session: SessionDep) -> None:
    # Its label directions go with it (ON DELETE CASCADE).
    session.delete(get_or_404(session, Product, product_id, "Product"))
    session.commit()

