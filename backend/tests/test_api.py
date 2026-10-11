import json

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app, get_plant_library
from app.plant_library import load_plants


@pytest.fixture
def library_dir(tmp_path, guide):
    """A plant directory with two valid guides: 'a-plant' and 'b-plant'."""
    for plant_id in ["b-plant", "a-plant"]:
        guide["id"] = plant_id
        (tmp_path / f"{plant_id}.json").write_text(json.dumps(guide), encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(library_dir):
    app.dependency_overrides[get_plant_library] = lambda: load_plants(library_dir)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_plants_returns_all_sorted_by_id(client):
    response = client.get("/plants")
    assert response.status_code == 200
    assert [plant["id"] for plant in response.json()] == ["a-plant", "b-plant"]


# Ask for the second plant, so returning the first one by mistake would fail.
def test_get_plant_returns_requested_plant(client):
    response = client.get("/plants/b-plant")
    assert response.status_code == 200
    assert response.json()["id"] == "b-plant"


def test_get_unknown_plant_returns_404(client):
    response = client.get("/plants/no-such-plant")
    assert response.status_code == 404


def test_load_plants_rejects_invalid_file(library_dir):
    (library_dir / "broken.json").write_text('{"id": "broken"}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_plants(library_dir)


def test_load_plants_rejects_duplicate_id(library_dir, guide):
    guide["id"] = "a-plant"
    (library_dir / "c-plant.json").write_text(json.dumps(guide), encoding="utf-8")
    with pytest.raises(ValueError):
        load_plants(library_dir)


def test_app_starts_with_real_library():
    with TestClient(app) as client:  # runs startup, which loads data/plants
        assert client.get("/health").json() == {"status": "ok"}


def test_app_fails_at_startup_with_invalid_library(tmp_path, monkeypatch):
    (tmp_path / "broken.json").write_text('{"id": "broken"}', encoding="utf-8")
    monkeypatch.setattr(main_module, "PLANTS_DIR", tmp_path)
    get_plant_library.cache_clear()
    try:
        with pytest.raises(ValueError):
            with TestClient(app):
                pass
    finally:
        get_plant_library.cache_clear()  # don't leak the broken library
