"""API tests for creating and reading products."""

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Product
from app.routers.products import commit_or_conflict


def create(client, product):
    return client.post("/products", json=product)


def without_saved_fields(body: dict) -> dict:
    return {key: value for key, value in body.items() if key not in ("id", "created_at")}


# --- POST /products


def test_create_returns_201_with_saved_product(client, product):
    response = create(client, product)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert "created_at" in body
    assert without_saved_fields(body) == product  # NPK comes back as numbers: 9, not "9"


def test_created_product_can_be_read_back(client, product):
    created = create(client, product).json()
    response = client.get(f"/products/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_invalid_product_returns_422_and_saves_nothing(client, product):
    del product["npk"]  # a fertilizer must have NPK
    response = create(client, product)
    assert response.status_code == 422
    assert client.get("/products").json() == []


@pytest.mark.parametrize(
    "brand, name",
    [("Dyna-Gro", "Foliage-Pro"), ("DYNA-GRO", "foliage-pro")],
    ids=["same", "different-case"],
)
def test_duplicate_brand_and_name_returns_409(client, product, brand, name):
    create(client, product)
    response = create(client, product | {"brand": brand, "name": name})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    assert len(client.get("/products").json()) == 1


def test_create_works_after_a_conflict(client, product):
    create(client, product)
    create(client, product)  # 409; its failed transaction must not linger
    response = create(client, product | {"name": "Grow"})
    assert response.status_code == 201


# --- GET /products


def test_list_is_empty_at_first(client):
    response = client.get("/products")
    assert response.status_code == 200
    assert response.json() == []


def test_list_is_sorted_by_brand_then_name_ignoring_case(client, product):
    for brand, name in [("b", "x"), ("A", "z"), ("a", "Y"), ("B", "w")]:
        create(client, product | {"brand": brand, "name": name})
    listed = [(p["brand"], p["name"]) for p in client.get("/products").json()]
    assert listed == [("a", "Y"), ("A", "z"), ("B", "w"), ("b", "x")]


def test_list_includes_label_directions(client, product):
    create(client, product)
    listed = client.get("/products").json()
    assert listed[0]["label_directions"] == product["label_directions"]


# --- GET /products/{id}


def test_get_unknown_product_returns_404(client):
    response = client.get("/products/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Product 999 not found"


def test_get_with_non_integer_id_returns_422(client):
    assert client.get("/products/abc").status_code == 422



# --- PUT /products/{id}


def replace(client, product_id, product):
    return client.put(f"/products/{product_id}", json=product)


def changed(product: dict) -> dict:
    """product with a new name, NPK, and a single direction."""
    return product | {
        "name": "Grow",
        "npk": {"n": 7, "p": 9, "k": 5, "basis": "elemental"},
        "label_directions": [
            {
                "amount": 5,
                "amount_unit": "ml",
                "water_volume": 1,
                "water_unit": "L",
                "frequency": {"kind": "interval", "days": 14},
            }
        ],
    }


def test_replace_returns_new_content_with_same_id_and_created_at(client, product):
    created = create(client, product).json()
    response = replace(client, created["id"], changed(product))
    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["created_at"]) == (created["id"], created["created_at"])
    assert without_saved_fields(body) == changed(product) | {
        "label_directions": [changed(product)["label_directions"][0] | {"use": None}]
    }


def test_replaced_product_is_read_back(client, product):
    created = create(client, product).json()
    replaced = replace(client, created["id"], changed(product)).json()
    assert client.get(f"/products/{created['id']}").json() == replaced


# Regression: label directions that keep their use and position used to hit
# the unique indexes, since a flush inserts before it deletes.
def test_replace_with_unchanged_content_succeeds(client, product):
    created = create(client, product).json()
    response = replace(client, created["id"], product)
    assert response.status_code == 200
    assert response.json() == created


def test_replace_can_remove_npk(client, product):
    created = create(client, product).json()
    del product["npk"]
    product["type"] = "additive"
    assert replace(client, created["id"], product).json()["npk"] is None


def test_replace_unknown_product_returns_404(client, product):
    assert replace(client, 999, product).status_code == 404


def test_replace_with_invalid_body_returns_422_and_keeps_product(client, product):
    created = create(client, product).json()
    response = replace(client, created["id"], product | {"label_directions": []})
    assert response.status_code == 422
    assert client.get(f"/products/{created['id']}").json() == created


def test_replace_into_another_products_name_returns_409_and_keeps_product(client, product):
    first = create(client, product).json()
    create(client, product | {"name": "Grow"})
    response = replace(client, first["id"], product | {"name": "GROW"})
    assert response.status_code == 409
    # The old directions were deleted and flushed before the failed commit;
    # the rollback must bring them back.
    assert client.get(f"/products/{first['id']}").json() == first


def test_replace_with_own_name_in_different_case_succeeds(client, product):
    created = create(client, product).json()
    response = replace(client, created["id"], product | {"name": "FOLIAGE-PRO"})
    assert response.status_code == 200
    assert response.json()["name"] == "FOLIAGE-PRO"


# --- DELETE /products/{id}


def test_delete_returns_204_and_removes_product(client, product):
    created = create(client, product).json()
    response = client.delete(f"/products/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/products/{created['id']}").status_code == 404


def test_delete_keeps_other_products(client, product):
    first = create(client, product).json()
    second = create(client, product | {"name": "Grow"}).json()
    client.delete(f"/products/{first['id']}")
    assert client.get("/products").json() == [second]


def test_delete_unknown_product_returns_404(client):
    assert client.delete("/products/999").status_code == 404

# --- commit_or_conflict: only a duplicate brand and name becomes 409
# (through the API, Pydantic rejects everything else first, so these call
# the function directly)


def add_raw(session, **fields):
    session.add(Product(**({"brand": "B", "name": "N", "type": "additive"} | fields)))


def test_commit_or_conflict_turns_duplicate_into_409(session):
    add_raw(session)
    session.commit()
    add_raw(session, brand="b")
    with pytest.raises(HTTPException) as caught:
        commit_or_conflict(session)
    assert caught.value.status_code == 409


def test_commit_or_conflict_reraises_other_integrity_errors(session):
    add_raw(session, type="slow_release")  # breaks a CHECK, not the unique index
    with pytest.raises(IntegrityError, match="valid_type"):
        commit_or_conflict(session)
