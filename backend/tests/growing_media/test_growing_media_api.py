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


# --- PUT /growing-media/{id}


def replace(client, medium_id, medium):
    return client.put(f"/growing-media/{medium_id}", json=medium)


def changed(medium: dict) -> dict:
    """medium as a semi-hydro LECA medium under a new name."""
    return medium | {
        "name": "LECA",
        "method": "semi_hydro",
        "components": [{"component": "leca", "parts": 1}],
        "notes": "",
    }


def test_replace_returns_new_content_with_same_id_and_created_at(client, medium):
    created = create(client, medium).json()
    response = replace(client, created["id"], changed(medium))
    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["created_at"]) == (created["id"], created["created_at"])
    assert without_saved_fields(body) == changed(medium)


def test_replaced_medium_is_read_back(client, medium):
    created = create(client, medium).json()
    replaced = replace(client, created["id"], changed(medium)).json()
    assert client.get(f"/growing-media/{created['id']}").json() == replaced


def test_replace_with_unchanged_content_succeeds(client, medium):
    created = create(client, medium).json()
    response = replace(client, created["id"], medium)
    assert response.status_code == 200
    assert response.json() == created


def test_replace_can_switch_to_hydro_without_components(client, medium):
    created = create(client, medium).json()
    body = replace(client, created["id"], medium | {"method": "hydro", "components": []}).json()
    assert (body["method"], body["components"]) == ("hydro", [])


def test_replace_unknown_medium_returns_404(client, medium):
    assert replace(client, 999, medium).status_code == 404


def test_replace_with_invalid_body_returns_422_and_keeps_medium(client, medium):
    created = create(client, medium).json()
    response = replace(client, created["id"], medium | {"components": []})  # soil needs one
    assert response.status_code == 422
    assert client.get(f"/growing-media/{created['id']}").json() == created


def test_replace_into_another_media_name_returns_409_and_keeps_medium(client, medium):
    first = create(client, medium).json()
    create(client, medium | {"name": "LECA"})
    response = replace(client, first["id"], medium | {"name": "leca"})
    assert response.status_code == 409
    # The old components were deleted before the failed commit; the
    # rollback must bring them back.
    assert client.get(f"/growing-media/{first['id']}").json() == first


def test_replace_with_own_name_in_different_case_succeeds(client, medium):
    created = create(client, medium).json()
    response = replace(client, created["id"], medium | {"name": "AROID MIX"})
    assert response.status_code == 200
    assert response.json()["name"] == "AROID MIX"


def test_replace_keeps_other_media_components(client, medium):
    first = create(client, medium).json()
    second = create(client, medium | {"name": "Other"}).json()  # not "LECA", which changed() takes
    assert replace(client, first["id"], changed(medium)).status_code == 200
    assert client.get(f"/growing-media/{second['id']}").json() == second


# --- DELETE /growing-media/{id}


def test_delete_returns_204_and_removes_medium(client, medium):
    created = create(client, medium).json()
    response = client.delete(f"/growing-media/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/growing-media/{created['id']}").status_code == 404


def test_delete_keeps_other_media(client, medium):
    first = create(client, medium).json()
    second = create(client, medium | {"name": "Other"}).json()
    client.delete(f"/growing-media/{first['id']}")
    assert client.get("/growing-media").json() == [second]


def test_delete_unknown_medium_returns_404(client):
    assert client.delete("/growing-media/999").status_code == 404
