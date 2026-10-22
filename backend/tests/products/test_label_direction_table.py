"""Database constraints on product_label_directions (Pydantic checks the same rules at the API)."""

from decimal import Decimal

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app.products.models import Product, ProductLabelDirection


def make_product(**fields):
    return Product(
        **{
            "brand": "Dyna-Gro",
            "name": "Foliage-Pro",
            "type": "liquid_fertilizer",
            "npk_n": Decimal("9"),
            "npk_p": Decimal("3"),
            "npk_k": Decimal("6"),
            "npk_basis": "oxide",
        }
        | fields
    )


def make_direction(**fields):
    return ProductLabelDirection(
        **{
            "position": 0,
            "application": "soil",
            "amount": 0.25,
            "amount_unit": "tsp",
            "water_volume": 1.0,
            "water_unit": "gal",
            "frequency_kind": "every_watering",
            "frequency_days": None,
            "use": "maintenance",
        }
        | fields
    )


@pytest.fixture
def product(session):
    product = make_product()
    session.add(product)
    session.commit()
    return product


def add_direction(session, product, **fields):
    direction = make_direction(**fields)
    product.label_directions.append(direction)
    session.commit()
    return direction


def rejected(session, product, constraint, **fields):
    product.label_directions.append(make_direction(**fields))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


def count_directions(session):
    return session.scalar(select(func.count()).select_from(ProductLabelDirection))


# --- valid rows and order


def test_both_frequency_kinds_round_trip(session, product):
    add_direction(session, product, position=0)
    add_direction(session, product, position=1, frequency_kind="interval", frequency_days=30, use="monthly")
    session.expire_all()  # force a fresh read from the database
    kinds = [(d.frequency_kind, d.frequency_days) for d in product.label_directions]
    assert kinds == [("every_watering", None), ("interval", 30)]


def test_directions_are_read_in_position_order(session, product):
    add_direction(session, product, position=1, use="second")
    add_direction(session, product, position=0, use="first")
    session.expire_all()
    assert [d.use for d in product.label_directions] == ["first", "second"]


# --- link to the product


def test_unknown_product_rejected(session):
    session.add(make_direction(product_id=999))
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


def test_deleting_product_deletes_its_directions(session, product):
    other = make_product(name="Grow")
    session.add(other)
    add_direction(session, product, position=0, use="a")
    add_direction(session, product, position=1, use="b")
    add_direction(session, other)

    session.delete(product)
    session.commit()

    assert count_directions(session) == 1  # only the other product's direction is left


def test_removing_direction_from_list_deletes_it(session, product):
    first = add_direction(session, product, position=0, use="a")
    add_direction(session, product, position=1, use="b")

    product.label_directions.remove(first)
    session.commit()

    assert count_directions(session) == 1


# Deletes cascade from product to directions only, never back up.
def test_deleting_direction_keeps_product(session, product):
    direction = add_direction(session, product)

    session.delete(direction)
    session.commit()
    session.expire_all()

    assert count_directions(session) == 0
    assert session.get(Product, product.id) is not None


# --- required columns


@pytest.mark.parametrize(
    "column",
    ["product_id", "position", "application", "amount", "amount_unit", "water_volume", "water_unit", "frequency_kind"],
)
def test_required_column(session, product, column):
    direction = make_direction(**({"product_id": product.id} | {column: None}))
    session.add(direction)
    with pytest.raises(IntegrityError, match=f"NOT NULL.*{column}"):
        session.commit()


# --- details


def test_details_default_to_empty(session, product):
    direction = add_direction(session, product)
    session.expire_all()
    assert direction.details == ""


# The ORM replaces None with the column's default, so the NULL is sent with a
# direct INSERT to reach the NOT NULL rule.
def test_details_cannot_be_null(session, product):
    row = {
        "product_id": product.id, "position": 0, "application": "soil", "amount": 0.25,
        "amount_unit": "tsp", "water_volume": 1.0, "water_unit": "gal",
        "frequency_kind": "every_watering", "details": None,
    }
    with pytest.raises(IntegrityError, match="NOT NULL.*details"):
        session.execute(insert(ProductLabelDirection).values(row))


# --- position


def test_negative_position_rejected(session, product):
    rejected(session, product, "position_not_negative", position=-1)


def test_duplicate_position_rejected(session, product):
    add_direction(session, product, position=0, use="a")
    rejected(session, product, "UNIQUE", position=0, use="b")


def test_same_position_on_other_product_accepted(session, product):
    other = make_product(name="Grow")
    session.add(other)
    add_direction(session, product, position=0)
    add_direction(session, other, position=0)


# --- application


@pytest.mark.parametrize("application", ["soil", "hydroponic", "foliar"])
def test_application_accepts_each_value(session, product, application):
    add_direction(session, product, application=application, frequency_kind="interval", frequency_days=14)


def test_unknown_application_rejected(session, product):
    rejected(session, product, "valid_application", application="drench")


def test_foliar_every_watering_rejected(session, product):
    rejected(session, product, "foliar_not_every_watering", application="foliar", frequency_kind="every_watering")


# --- amounts and units


@pytest.mark.parametrize("bad", [0, -1])
@pytest.mark.parametrize(
    "column, constraint",
    [("amount", "amount_positive"), ("water_volume", "water_volume_positive")],
)
def test_amount_must_be_positive(session, product, column, constraint, bad):
    rejected(session, product, constraint, **{column: bad})


@pytest.mark.parametrize(
    "column, bad_unit, constraint",
    [("amount_unit", "cup", "valid_amount_unit"), ("water_unit", "ml", "valid_water_unit")],
)
def test_unknown_unit_rejected(session, product, column, bad_unit, constraint):
    rejected(session, product, constraint, **{column: bad_unit})


# --- frequency: days only for "interval"


@pytest.mark.parametrize(
    "kind, days",
    [("interval", None), ("interval", 0), ("every_watering", 7), ("as_needed", 7), ("monthly", None), ("monthly", 30)],
    ids=["interval-no-days", "interval-zero-days", "every-watering-with-days", "as-needed-with-days", "unknown-kind", "unknown-kind-with-days"],
)
def test_invalid_frequency_rejected(session, product, kind, days):
    rejected(session, product, "valid_frequency", frequency_kind=kind, frequency_days=days)


def test_interval_accepts_one_day(session, product):
    add_direction(session, product, frequency_kind="interval", frequency_days=1)


def test_as_needed_accepted(session, product):
    add_direction(session, product, frequency_kind="as_needed", frequency_days=None)


# --- use


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_use_rejected(session, product, blank):
    rejected(session, product, "use_not_blank", use=blank)


@pytest.mark.parametrize("second", ["maintenance", "MAINTENANCE"], ids=["same", "different-case"])
def test_duplicate_use_in_product_rejected(session, product, second):
    add_direction(session, product, position=0, use="maintenance")
    rejected(session, product, "UNIQUE", position=1, use=second)


def test_same_use_in_other_application_accepted(session, product):
    add_direction(session, product, position=0, application="soil")
    add_direction(session, product, position=1, application="hydroponic")
    assert count_directions(session) == 2


def test_same_use_on_other_product_accepted(session, product):
    other = make_product(name="Grow")
    session.add(other)
    add_direction(session, product)
    add_direction(session, other)


# The rule "several directions each need a use" spans rows, so only Pydantic
# enforces it; the database allows several unnamed directions.
def test_several_unnamed_directions_allowed_in_database(session, product):
    add_direction(session, product, position=0, use=None)
    add_direction(session, product, position=1, use=None)
    assert count_directions(session) == 2
