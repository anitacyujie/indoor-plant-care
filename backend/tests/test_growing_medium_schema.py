"""Rules for a growing medium as a whole (single components: test_medium_component_schema.py)."""

import pytest
from pydantic import ValidationError

from app.schemas import GrowingMediumCreate, ListedMediumComponent, OtherMediumComponent


def rejects(data):
    with pytest.raises(ValidationError):
        GrowingMediumCreate.model_validate(data)


def other(name, parts=1):
    return {"component": "other", "name": name, "parts": parts}


# --- the medium itself


def test_valid_medium_passes(medium):
    result = GrowingMediumCreate.model_validate(medium)
    assert [type(c) for c in result.components] == [
        ListedMediumComponent,
        ListedMediumComponent,
        OtherMediumComponent,
    ]


@pytest.mark.parametrize("blank", ["", "   "])
def test_name_rejects_blank(medium, blank):
    medium["name"] = blank
    rejects(medium)


def test_name_is_stripped(medium):
    medium["name"] = "  Aroid mix  "
    assert GrowingMediumCreate.model_validate(medium).name == "Aroid mix"


@pytest.mark.parametrize("field", ["name", "method"])
def test_required_field_missing_rejected(medium, field):
    del medium[field]
    rejects(medium)


def test_notes_default_to_empty(medium):
    del medium["notes"]
    assert GrowingMediumCreate.model_validate(medium).notes == ""


@pytest.mark.parametrize("field", ["unknown_field", "soil"])  # "soil": a stale field name
def test_unknown_field_rejected(medium, field):
    medium[field] = "typo or stale field"
    rejects(medium)


def test_invalid_component_rejected(medium):
    medium["components"][0]["parts"] = 0  # checked by MediumComponent, reaches the medium
    rejects(medium)


# --- method and components


@pytest.mark.parametrize("method", ["soil", "semi_hydro", "hydro"])
def test_each_method_accepted_with_components(medium, method):
    medium["method"] = method
    assert GrowingMediumCreate.model_validate(medium).method == method


@pytest.mark.parametrize("bad_method", ["water", "Soil", "semi-hydro", ""])
def test_unknown_method_rejected(medium, bad_method):
    medium["method"] = bad_method
    rejects(medium)


@pytest.mark.parametrize("method", ["soil", "semi_hydro"])
def test_method_needs_a_component(medium, method):
    medium["method"] = method
    medium["components"] = []
    rejects(medium)


@pytest.mark.parametrize("empty", [[], None], ids=["empty-list", "omitted"])
def test_hydro_may_have_no_components(medium, empty):
    medium["method"] = "hydro"
    if empty is None:
        del medium["components"]
    else:
        medium["components"] = empty
    assert GrowingMediumCreate.model_validate(medium).components == []


# --- each material appears once


def test_duplicate_listed_component_rejected(medium):
    medium["components"].append({"component": "bark", "parts": 1})
    rejects(medium)


@pytest.mark.parametrize(
    "second",
    ["zeolite", "Zeolite", "ZEOLITE"],
    ids=["same", "different-case", "upper-case"],
)
def test_duplicate_other_name_rejected(medium, second):
    medium["components"].append(other(second))
    rejects(medium)


@pytest.mark.parametrize(
    "first, second",
    [("rice hulls", "Rice-Hulls"), ("rice hulls", "rice_hulls")],
    ids=["space-vs-hyphen", "space-vs-underscore"],
)
def test_other_names_compared_with_spaces_and_hyphens_as_underscores(medium, first, second):
    medium["components"] += [other(first), other(second)]
    rejects(medium)


def test_different_other_names_accepted(medium):
    medium["components"].append(other("rice hulls"))
    GrowingMediumCreate.model_validate(medium)


# The clash is with the whole list, not only the components in this medium:
# "Coco coir" is rejected although this medium has no coco_coir.
@pytest.mark.parametrize("name", ["Pumice", "coco coir", "Coco-Coir", "potting soil"])
def test_other_named_like_a_listed_component_rejected(medium, name):
    medium["components"][2] = other(name)
    rejects(medium)
