"""Rules for the taxa reference list (genera and families users pick for groups)."""

import copy
import json

import pytest
from pydantic import ValidationError

from app.schemas import TaxaList
from app.taxa import load_taxa

VALID_TAXA = {
    "sources": [
        {"id": "extension-list", "title": "A houseplant list", "url": "https://example.com/list"},
        {"id": "trend-report", "title": "A trend report", "url": "https://example.com/trends"},
    ],
    "families": [
        {"id": "araceae", "name": "Araceae", "common_names": {"en": ["arum family"], "zh": ["天南星科"]}},
        {"id": "asparagaceae", "name": "Asparagaceae", "common_names": {"zh": ["天门冬科"]}},
    ],
    "genera": [
        {
            "id": "monstera",
            "name": "Monstera",
            "family": "araceae",
            "common_names": {"en": ["monstera", "Swiss cheese plant"], "zh": ["龟背竹"]},
            "source_ids": ["extension-list", "trend-report"],
        },
        {
            "id": "dracaena",
            "name": "Dracaena",
            "family": "asparagaceae",
            "common_names": {"en": ["dracaena"], "zh": ["龙血树"]},
            "source_ids": ["extension-list"],
        },
        {
            "id": "sansevieria",
            "name": "Sansevieria",
            "family": "asparagaceae",
            "aliases": ["Dracaena"],  # the same name as another genus, on purpose
            "common_names": {"en": ["snake plant"], "zh": ["虎尾兰"]},
            "source_ids": ["extension-list"],
        },
    ],
}


@pytest.fixture
def taxa():
    return copy.deepcopy(VALID_TAXA)


def rejects(data):
    with pytest.raises(ValidationError):
        TaxaList.model_validate(data)


def monstera(taxa):
    return taxa["genera"][0]


def araceae(taxa):
    return taxa["families"][0]


# --- valid list and loading


def test_valid_list_passes(taxa):
    result = TaxaList.model_validate(taxa)
    assert [genus.id for genus in result.genera] == ["monstera", "dracaena", "sansevieria"]


def test_load_taxa_reads_file(tmp_path, taxa):
    path = tmp_path / "taxa.json"
    path.write_text(json.dumps(taxa, ensure_ascii=False), encoding="utf-8")
    assert load_taxa(path).genera[0].common_names.zh == ["龟背竹"]


def test_load_taxa_rejects_invalid_file(tmp_path, taxa):
    del taxa["genera"][0]["family"]
    path = tmp_path / "taxa.json"
    path.write_text(json.dumps(taxa), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_taxa(path)


# Non-empty families imply non-empty genera and sources (every family needs a
# genus, every genus a source), so an empty list is the one case to test.
def test_empty_list_rejected():
    rejects({"sources": [], "families": [], "genera": []})


# --- names and ids


# Each bad name still lowercases to a valid id, so only the name rule can
# reject it (e.g. "Monstera deliciosa" would also break the id rule).
@pytest.mark.parametrize("bad_name", ["monstera", "MONSTERA", "Monstera1"])
def test_genus_name_must_be_one_capitalized_word(taxa, bad_name):
    monstera(taxa)["name"] = bad_name
    monstera(taxa)["id"] = bad_name.lower()
    rejects(taxa)


@pytest.mark.parametrize("bad_name", ["Arum", "araceae", "ARACEAE"])
def test_family_name_must_end_in_aceae(taxa, bad_name):
    araceae(taxa)["name"] = bad_name
    araceae(taxa)["id"] = bad_name.lower()
    for genus in taxa["genera"]:
        if genus["family"] == "araceae":
            genus["family"] = bad_name.lower()
    rejects(taxa)


@pytest.mark.parametrize("taxon", ["genus", "family"])
def test_id_must_be_lowercased_name(taxa, taxon):
    entry = monstera(taxa) if taxon == "genus" else araceae(taxa)
    entry["id"] = "something-else"
    if taxon == "family":
        monstera(taxa)["family"] = "something-else"
    rejects(taxa)


def test_genus_and_family_ids_must_not_collide(taxa):
    # A genus whose id is also a family id, with a name that matches its id.
    taxa["genera"].append(
        monstera(taxa) | {"id": "araceae", "name": "Araceae", "common_names": {"en": ["x"], "zh": ["x"]}}
    )
    rejects(taxa)


def test_duplicate_genus_rejected(taxa):
    taxa["genera"].append(copy.deepcopy(monstera(taxa)))
    rejects(taxa)


def test_duplicate_source_id_rejected(taxa):
    taxa["sources"].append(copy.deepcopy(taxa["sources"][0]))
    rejects(taxa)


@pytest.mark.parametrize("bad_url", ["not-a-url", "example.com", ""])
def test_source_url_must_be_valid(taxa, bad_url):
    taxa["sources"][0]["url"] = bad_url
    rejects(taxa)


# --- references between sections


# Sansevieria, not Monstera: Dracaena keeps Asparagaceae in use, so the
# "family without genera" rule cannot reject the data instead.
def test_unknown_family_rejected(taxa):
    taxa["genera"][2]["family"] = "orchidaceae"
    rejects(taxa)


def test_family_must_be_a_family_not_a_genus(taxa):
    taxa["genera"][2]["family"] = "dracaena"
    rejects(taxa)


def test_family_without_genera_rejected(taxa):
    taxa["families"].append(
        {"id": "orchidaceae", "name": "Orchidaceae", "common_names": {"zh": ["兰科"]}}
    )
    rejects(taxa)


def test_source_ids_required(taxa):
    monstera(taxa)["source_ids"] = []
    rejects(taxa)


def test_unknown_source_id_rejected(taxa):
    monstera(taxa)["source_ids"] = ["extension-list", "missing"]
    rejects(taxa)


# --- common names


@pytest.mark.parametrize("language", ["en", "zh"])
def test_genus_needs_common_name_in_each_language(taxa, language):
    monstera(taxa)["common_names"][language] = []
    rejects(taxa)


def test_family_needs_chinese_name(taxa):
    araceae(taxa)["common_names"]["zh"] = []
    rejects(taxa)


def test_family_english_name_is_optional(taxa):
    del araceae(taxa)["common_names"]["en"]
    assert TaxaList.model_validate(taxa).families[0].common_names.en == []


@pytest.mark.parametrize(
    "taxon, language",
    [("genus", "en"), ("genus", "zh"), ("family", "en"), ("family", "zh")],
)
def test_duplicate_common_name_rejected(taxa, taxon, language):
    names = (monstera(taxa) if taxon == "genus" else araceae(taxa))["common_names"]
    names[language] = ["Name", "name"]  # same ignoring case
    rejects(taxa)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_common_name_rejected(taxa, blank):
    monstera(taxa)["common_names"]["zh"] = [blank]
    rejects(taxa)


def test_same_common_name_in_two_genera_accepted(taxa):
    taxa["genera"][1]["common_names"]["en"] = ["snake plant"]  # dracaena, like sansevieria
    TaxaList.model_validate(taxa)


# --- aliases


def test_alias_may_be_another_genus_name(taxa):
    result = TaxaList.model_validate(taxa)
    assert result.genera[2].aliases == ["Dracaena"]


@pytest.mark.parametrize("bad_alias", ["goeppertia", "Goeppertia orbifolia", ""])
def test_alias_must_be_a_genus_name(taxa, bad_alias):
    monstera(taxa)["aliases"] = [bad_alias]
    rejects(taxa)


def test_duplicate_alias_rejected(taxa):
    monstera(taxa)["aliases"] = ["Thaumatophyllum", "Thaumatophyllum"]
    rejects(taxa)


def test_genus_cannot_be_its_own_alias(taxa):
    monstera(taxa)["aliases"] = ["Monstera"]
    rejects(taxa)


# --- unknown fields


@pytest.mark.parametrize(
    "where",
    ["top-level", "source", "family", "family-common-names", "genus", "genus-common-names"],
)
def test_unknown_field_rejected(taxa, where):
    target = {
        "top-level": taxa,
        "source": taxa["sources"][0],
        "family": araceae(taxa),
        "family-common-names": araceae(taxa)["common_names"],
        "genus": monstera(taxa),
        "genus-common-names": monstera(taxa)["common_names"],
    }[where]
    target["unknown_field"] = "typo or stale field"
    rejects(taxa)
