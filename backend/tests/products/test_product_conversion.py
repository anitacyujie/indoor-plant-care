"""Conversion between the API shape (ProductCreate / ProductRead) and the tables."""

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.products.models import Product, ProductLabelDirection
from app.products.router import fill_product, product_to_read
from app.products.schemas import ProductCreate


def save_and_reload(session, data: dict) -> Product:
    product = fill_product(Product(), ProductCreate.model_validate(data))
    session.add(product)
    session.commit()
    session.expire_all()  # force a fresh read from the database
    return product


def without_saved_fields(read) -> dict:
    return read.model_dump(exclude={"id", "created_at"})


# --- round trip: what goes in comes back out


def test_full_product_round_trips(session, product):
    read = product_to_read(save_and_reload(session, product))
    assert without_saved_fields(read) == ProductCreate.model_validate(product).model_dump()


def test_additive_without_npk_round_trips(session, product):
    product["type"] = "additive"
    del product["npk"]
    read = product_to_read(save_and_reload(session, product))
    assert read.npk is None
    assert without_saved_fields(read) == ProductCreate.model_validate(product).model_dump()


def test_read_includes_id_and_created_at(session, product):
    read = product_to_read(save_and_reload(session, product))
    assert read.id == 1
    assert isinstance(read.created_at, datetime)


# --- how the nested API shape maps to flat columns


def test_npk_maps_to_four_columns(session, product):
    product["npk"] = {"n": 0.25, "p": 3, "k": 15.9, "basis": "elemental"}
    saved = save_and_reload(session, product)
    columns = (saved.npk_n, saved.npk_p, saved.npk_k, saved.npk_basis)
    assert columns == (Decimal("0.25"), Decimal("3"), Decimal("15.9"), "elemental")


def test_frequency_maps_to_kind_and_days(session, product):
    saved = save_and_reload(session, product)
    columns = [(d.frequency_kind, d.frequency_days) for d in saved.label_directions]
    assert columns == [("every_watering", None), ("interval", 30)]


def test_application_maps_to_its_column(session, product):
    product["label_directions"][1]["application"] = "foliar"
    saved = save_and_reload(session, product)
    assert [d.application for d in saved.label_directions] == ["soil", "foliar"]
    assert [d.application for d in product_to_read(saved).label_directions] == ["soil", "foliar"]


def test_directions_keep_their_order(session, product):
    third = dict(product["label_directions"][0], use="third")
    product["label_directions"].append(third)
    saved = save_and_reload(session, product)
    assert [d.position for d in saved.label_directions] == [0, 1, 2]
    assert [d.use for d in product_to_read(saved).label_directions] == [
        "maintenance",
        "monthly feeding",
        "third",
    ]


# --- update: filling an existing product replaces it


def test_fill_existing_product_replaces_fields_and_directions(session, product):
    saved = save_and_reload(session, product)
    product["name"] = "Grow"
    product["label_directions"] = product["label_directions"][:1]

    fill_product(saved, ProductCreate.model_validate(product))
    session.commit()
    session.expire_all()

    assert saved.name == "Grow"
    assert [d.use for d in saved.label_directions] == ["maintenance"]
    # Old rows are deleted, not left behind without a product.
    assert session.scalar(select(func.count()).select_from(ProductLabelDirection)) == 1


def test_fill_existing_product_with_same_directions(session, product):
    saved = save_and_reload(session, product)
    fill_product(saved, ProductCreate.model_validate(product))
    session.commit()
    assert len(saved.label_directions) == 2


# Updating rows in place would also collide here: row 0 takes "b" while row 1
# still has it.
def test_fill_existing_product_with_swapped_uses(session, product):
    saved = save_and_reload(session, product)
    first, second = product["label_directions"]
    first["use"], second["use"] = second["use"], first["use"]

    fill_product(saved, ProductCreate.model_validate(product))
    session.commit()
    session.expire_all()

    assert [d.use for d in saved.label_directions] == ["monthly feeding", "maintenance"]


def test_fill_existing_product_can_remove_npk(session, product):
    saved = save_and_reload(session, product)
    product["type"] = "additive"
    del product["npk"]

    fill_product(saved, ProductCreate.model_validate(product))
    session.commit()

    assert (saved.npk_n, saved.npk_p, saved.npk_k, saved.npk_basis) == (None, None, None, None)


# --- JSON output


def test_npk_is_a_json_number(session, product):
    product["npk"] = {"n": 9, "p": 0.25, "k": 15.9, "basis": "oxide"}
    read = product_to_read(save_and_reload(session, product))
    npk = json.loads(read.model_dump_json())["npk"]
    assert npk == {"n": 9, "p": 0.25, "k": 15.9, "basis": "oxide"}
    assert isinstance(npk["n"], int)  # whole numbers print as 9, not 9.0
