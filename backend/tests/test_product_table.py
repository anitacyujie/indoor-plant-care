"""Database constraints on the products table (Pydantic checks the same rules at the API)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Product

NPK = {"npk_n": Decimal("9"), "npk_p": Decimal("3"), "npk_k": Decimal("6"), "npk_basis": "oxide"}


def make_product(**fields):
    return Product(**({"brand": "Dyna-Gro", "name": "Foliage-Pro", "type": "liquid_fertilizer"} | NPK | fields))


def save(session, product):
    session.add(product)
    session.commit()
    return product


def rejected(session, product, constraint):
    session.add(product)
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


def test_valid_product_round_trips(session):
    before = datetime.now(UTC)
    product = save(session, make_product(npk_n=Decimal("0.25")))
    session.expire_all()  # force a fresh read from the database
    assert product.id == 1
    assert (product.npk_n, product.npk_p, product.npk_k) == (Decimal("0.25"), Decimal("3"), Decimal("6"))
    assert product.notes == ""
    assert before <= product.created_at <= datetime.now(UTC)


@pytest.mark.parametrize("missing", ["brand", "name", "type"])
def test_required_column(session, missing):
    product = make_product()
    setattr(product, missing, None)
    rejected(session, product, f"NOT NULL.*{missing}")


@pytest.mark.parametrize("field", ["brand", "name"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_text_rejected(session, field, blank):
    rejected(session, make_product(**{field: blank}), f"{field}_not_blank")


def test_unknown_type_rejected(session):
    rejected(session, make_product(type="slow_release"), "valid_type")


def test_unknown_basis_rejected(session):
    rejected(session, make_product(npk_basis="metric"), "valid_npk_basis")


@pytest.mark.parametrize("missing", ["npk_n", "npk_p", "npk_k", "npk_basis"])
def test_npk_is_all_or_none(session, missing):
    # An additive, so fertilizer_has_npk cannot reject it instead.
    rejected(session, make_product(type="additive", **{missing: None}), "npk_all_or_none")


@pytest.mark.parametrize("nutrient", ["npk_n", "npk_p", "npk_k"])
@pytest.mark.parametrize("value", ["-0.01", "100.01"])
def test_npk_out_of_range_rejected(session, nutrient, value):
    rejected(session, make_product(**{nutrient: Decimal(value)}), "npk_in_range")


@pytest.mark.parametrize("value", ["0", "100"])
def test_npk_range_boundaries_accepted(session, value):
    save(session, make_product(npk_n=Decimal(value), npk_p=Decimal(value), npk_k=Decimal(value)))


@pytest.mark.parametrize("fertilizer_type", ["liquid_fertilizer", "soluble_powder"])
def test_fertilizer_without_npk_rejected(session, fertilizer_type):
    no_npk = dict.fromkeys(NPK)
    rejected(session, make_product(type=fertilizer_type, **no_npk), "fertilizer_has_npk")


def test_additive_without_npk_accepted(session):
    product = save(session, make_product(type="additive", **dict.fromkeys(NPK)))
    assert product.npk_basis is None


@pytest.mark.parametrize(
    "brand, name",
    [("Dyna-Gro", "Foliage-Pro"), ("dyna-gro", "FOLIAGE-PRO")],
    ids=["same", "different-case"],
)
def test_duplicate_brand_and_name_rejected(session, brand, name):
    save(session, make_product())
    rejected(session, make_product(brand=brand, name=name), "UNIQUE")


@pytest.mark.parametrize(
    "fields", [{"name": "Grow"}, {"brand": "Other"}], ids=["same-brand", "same-name"]
)
def test_same_brand_or_name_alone_accepted(session, fields):
    save(session, make_product())
    save(session, make_product(**fields))
