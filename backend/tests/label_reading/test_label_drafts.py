"""From what the model read off a label (LabelExtraction) to a product draft."""

import copy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.label_reading.drafts import draft_from_extraction
from app.label_reading.schemas import LabelExtraction

DIRECTION = {
    "source_text": "1/4 tsp per gallon every watering",
    "amount": 0.25,
    "amount_unit": "tsp",
    "water_volume": 1,
    "water_unit": "gal",
    "frequency_kind": "every_watering",
    "frequency_days": None,
    "use": None,
}

# A label read completely: one direction, NPK with its basis.
COMPLETE = {
    "brand": "Dyna-Gro",
    "name": "Foliage-Pro",
    "type": "liquid_fertilizer",
    "npk": {"n": 9, "p": 3, "k": 6},
    "npk_basis": "oxide",
    "label_directions": [DIRECTION],
    "notes": "Urea-free.",
    "uncertain_fields": [],
    "lower_end_fields": [],
    "skipped_directions": [],
}


@pytest.fixture
def extraction():
    return copy.deepcopy(COMPLETE)


def draft(data):
    return draft_from_extraction(LabelExtraction.model_validate(data))


def problems(data):
    return [(p.location, p.message) for p in draft(data).problems]


def locations(data):
    return [location for location, _ in problems(data)]


# --- a complete label becomes a product


def test_complete_label_gives_a_draft_ready_to_save(extraction):
    result = draft(extraction)
    assert result.problems == []
    product = result.product
    assert (product.brand, product.name, product.type) == ("Dyna-Gro", "Foliage-Pro", "liquid_fertilizer")
    assert product.npk.basis == "oxide"
    assert product.notes == "Urea-free."
    direction = product.label_directions[0]
    assert (direction.amount, direction.amount_unit, direction.frequency.kind) == (0.25, "tsp", "every_watering")


def test_extraction_is_returned_unchanged(extraction):
    assert draft(extraction).extraction.model_dump() == extraction


def test_npk_values_come_through_exactly(extraction):
    extraction["npk"] = {"n": 0.2, "p": 83.9, "k": 15.9}
    npk = draft(extraction).product.npk
    assert (npk.n, npk.p, npk.k) == (Decimal("0.2"), Decimal("83.9"), Decimal("15.9"))


def test_interval_frequency_is_mapped(extraction):
    extraction["label_directions"][0] |= {"frequency_kind": "interval", "frequency_days": 14}
    frequency = draft(extraction).product.label_directions[0].frequency
    assert (frequency.kind, frequency.days) == ("interval", 14)



def test_named_directions_keep_their_use(extraction):
    monthly = DIRECTION | {"frequency_kind": "interval", "frequency_days": 30, "use": "monthly"}
    extraction["label_directions"] = [DIRECTION | {"use": "maintenance"}, monthly]
    uses = [d.use for d in draft(extraction).product.label_directions]
    assert uses == ["maintenance", "monthly"]

def test_missing_notes_become_empty(extraction):
    extraction["notes"] = None
    assert draft(extraction).product.notes == ""


def test_additive_without_npk_gives_a_draft_ready_to_save(extraction):
    extraction |= {"type": "additive", "npk": None, "npk_basis": None}
    assert draft(extraction).product.npk is None


def test_uncertain_fields_do_not_block_a_ready_draft(extraction):
    extraction["uncertain_fields"] = ["npk.p"]
    result = draft(extraction)
    assert result.product is not None
    assert result.extraction.uncertain_fields == ["npk.p"]



# Notes for the user: they change nothing about the draft itself.
def test_lower_end_and_skipped_directions_do_not_block_a_ready_draft(extraction):
    extraction["lower_end_fields"] = ["label_directions.0.amount"]
    extraction["skipped_directions"] = [{"source_text": "SIPHON MIXER: 1-3 fl. oz.", "reason": "equipment"}]
    result = draft(extraction)
    assert result.product is not None
    assert result.extraction.lower_end_fields == ["label_directions.0.amount"]
    assert result.extraction.skipped_directions[0].reason == "equipment"
    assert len(result.product.label_directions) == 1  # a skipped direction never becomes one

# --- what the label did not show becomes a problem, never a guess


@pytest.mark.parametrize("field", ["brand", "name", "type"])
def test_missing_top_level_field_is_a_problem(extraction, field):
    extraction[field] = None
    result = draft(extraction)
    assert result.product is None
    assert locations(extraction) == [field]


def test_missing_basis_is_a_problem(extraction):
    extraction["npk_basis"] = None
    assert locations(extraction) == ["npk.basis"]


@pytest.mark.parametrize("nutrient", ["n", "p", "k"])
def test_unreadable_npk_value_is_a_problem(extraction, nutrient):
    extraction["npk"][nutrient] = None
    assert locations(extraction) == [f"npk.{nutrient}"]


def test_fertilizer_without_npk_is_a_product_level_problem(extraction):
    extraction |= {"npk": None, "npk_basis": None}
    [(location, message)] = problems(extraction)
    assert location == "product"
    assert "NPK" in message


@pytest.mark.parametrize("field", ["amount", "amount_unit", "water_volume", "water_unit"])
def test_missing_dose_field_is_a_problem(extraction, field):
    extraction["label_directions"][0][field] = None  # e.g. a unit like "capful"
    assert locations(extraction) == [f"label_directions.0.{field}"]


def test_missing_frequency_is_a_problem(extraction):
    extraction["label_directions"][0]["frequency_kind"] = None
    assert locations(extraction) == ["label_directions.0.frequency"]


def test_interval_without_days_is_a_problem(extraction):
    extraction["label_directions"][0]["frequency_kind"] = "interval"
    assert locations(extraction) == ["label_directions.0.frequency.interval.days"]


def test_label_without_directions_is_a_problem(extraction):
    extraction["label_directions"] = []
    assert locations(extraction) == ["label_directions"]


def test_several_unnamed_directions_are_a_product_level_problem(extraction):
    extraction["label_directions"] = [DIRECTION, DIRECTION]
    [(location, message)] = problems(extraction)
    assert location == "product"
    assert "use" in message


# Rounding 0.125 to 0.12 would change what the label says without telling anyone.
def test_value_with_three_decimals_is_reported_not_rounded(extraction):
    extraction["npk"]["n"] = 0.125
    assert locations(extraction) == ["npk.n"]


def test_several_problems_are_all_reported(extraction):
    extraction |= {"brand": None, "npk_basis": None}
    extraction["label_directions"][0]["amount_unit"] = None
    assert sorted(locations(extraction)) == ["brand", "label_directions.0.amount_unit", "npk.basis"]


# --- the extraction schema itself (also the model's output format)


def test_extraction_rejects_unknown_fields(extraction):
    extraction["guess"] = "anything"
    with pytest.raises(ValidationError):
        LabelExtraction.model_validate(extraction)



@pytest.mark.parametrize("reason", ["outdoor", "equipment", "foliar", "other"])
def test_skipped_direction_accepts_each_reason(extraction, reason):
    extraction["skipped_directions"] = [{"source_text": "x", "reason": reason}]
    LabelExtraction.model_validate(extraction)


@pytest.mark.parametrize("reason", ["hydroponic", "Outdoor", None])
def test_skipped_direction_rejects_unknown_reason(extraction, reason):
    extraction["skipped_directions"] = [{"source_text": "x", "reason": reason}]
    with pytest.raises(ValidationError):
        LabelExtraction.model_validate(extraction)

# Structured outputs need every object closed and every field listed as
# required (null stands for "not on the label").
def test_extraction_schema_is_closed_and_fully_required():
    schema = LabelExtraction.model_json_schema()
    assert set(schema["$defs"]) == {"ExtractedNpk", "ExtractedDirection", "SkippedDirection"}
    objects = [schema, *schema["$defs"].values()]
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
