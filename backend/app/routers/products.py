"""Product endpoints, and conversion between the API shape and the tables.

The API nests what the tables keep flat (npk -> four columns, frequency ->
kind and days), so conversion is written out by hand in both directions.
"""

from sqlalchemy.orm import object_session

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
    Replaced directions are deleted on commit (delete-orphan).
    """
    product.brand = data.brand
    product.name = data.name
    product.type = data.type
    product.notes = data.notes

    npk = data.npk
    product.npk_n = npk.n if npk else None
    product.npk_p = npk.p if npk else None
    product.npk_k = npk.k if npk else None
    product.npk_basis = npk.basis if npk else None

    # On update, delete the old directions before adding the new ones. A
    # flush otherwise inserts before it deletes, so a direction that keeps
    # its use or position would collide with the row it replaces under the
    # unique indexes.
    session = object_session(product)
    if session is not None and product.label_directions:
        product.label_directions.clear()
        session.flush()

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
