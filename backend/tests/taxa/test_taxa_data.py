"""The real taxa list in backend/data/taxa.json, and loading it at startup."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.taxa.loader as taxa_module
from app.main import app
from app.taxa.loader import TAXA_FILE, get_taxa, load_taxa


def test_taxa_file_is_valid():
    load_taxa(TAXA_FILE)


# Sorted entries keep diffs small when the list is edited by hand.
@pytest.mark.parametrize("section", ["families", "genera"])
def test_entries_are_sorted_by_name(section):
    names = [entry.name for entry in getattr(load_taxa(TAXA_FILE), section)]
    assert names == sorted(names)


def test_get_taxa_loads_once():
    assert get_taxa() is get_taxa()


def test_app_starts_with_real_taxa():
    with TestClient(app) as client:  # runs startup, which loads taxa.json
        assert client.get("/health").json() == {"status": "ok"}


def test_app_fails_at_startup_with_invalid_taxa(tmp_path, monkeypatch):
    broken = tmp_path / "taxa.json"
    broken.write_text('{"sources": [], "families": [], "genera": []}', encoding="utf-8")
    monkeypatch.setattr(taxa_module, "TAXA_FILE", broken)
    get_taxa.cache_clear()
    try:
        with pytest.raises(ValidationError):
            with TestClient(app):
                pass
    finally:
        get_taxa.cache_clear()  # don't leak the broken list into other tests
