"""API tests for creating and reading growing media."""

import pytest


def create(client, medium):
    return client.post("/growing-media", json=medium)


def without_saved_fields(body: dict) -> dict:
    return {key: value for key, value in body.items() if key not in ("id", "created_at")}


# --- POST /growing-media


def test_create_returns_201_with_saved_medium(client, medium):
    response = create(client, medium)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert "created_at" in body
    assert without_saved_fields(body) == medium


def test_created_medium_can_be_read_back(client, medium):
    created = create(client, medium).json()
    response = client.get(f"/growing-media/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_invalid_medium_returns_422_and_saves_nothing(client, medium):
    medium["components"] = []  # a soil medium needs a component
    assert create(client, medium).status_code == 422
    assert client.get("/growing-media").json() == []


@pytest.mark.parametrize("name", ["Aroid mix", "AROID MIX"], ids=["same", "different-case"])
def test_duplicate_name_returns_409(client, medium, name):
    create(client, medium)
    response = create(client, medium | {"name": name})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    assert len(client.get("/growing-media").json()) == 1


def test_create_works_after_a_conflict(client, medium):
    create(client, medium)
    create(client, medium)  # 409
    assert create(client, medium | {"name": "Hoya mix"}).status_code == 201


# --- GET /growing-media


def test_list_is_empty_at_first(client):
    response = client.get("/growing-media")
    assert response.status_code == 200
    assert response.json() == []


# Case-sensitive order would be A, C, b (capitals sort first).
def test_list_is_sorted_by_name_ignoring_case(client, medium):
    for name in ["b", "A", "C"]:
        create(client, medium | {"name": name})
    assert [m["name"] for m in client.get("/growing-media").json()] == ["A", "b", "C"]


def test_list_includes_components(client, medium):
    create(client, medium)
    assert client.get("/growing-media").json()[0]["components"] == medium["components"]


# --- GET /growing-media/{id}


def test_get_unknown_medium_returns_404(client):
    response = client.get("/growing-media/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Growing medium 999 not found"


def test_get_with_non_integer_id_returns_422(client):
    assert client.get("/growing-media/abc").status_code == 422
