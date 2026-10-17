from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    EveryWateringFrequency,
    IntervalFrequency,
    LabelFrequency,
    Npk,
    ProductCreate,
)


def set_field(data, path, value):
    """Set a nested value, e.g. path ("npk", "n") sets data["npk"]["n"]."""
    *parents, last = path
    for key in parents:
        data = data[key]
    data[last] = value


def rejects(data):
    with pytest.raises(ValidationError):
        ProductCreate.model_validate(data)


VALID_NPK = {"n": 9, "p": 3, "k": 6, "basis": "oxide"}


# --- ProductCreate: the whole product


def test_valid_product_passes(product):
    result = ProductCreate.model_validate(product)
    assert result.npk.n == Decimal("9")
    assert isinstance(result.label_directions[0].frequency, EveryWateringFrequency)
    assert isinstance(result.label_directions[1].frequency, IntervalFrequency)


@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("field", ["brand", "name"])
def test_required_text_rejects_blank(product, field, blank):
    product[field] = blank
    rejects(product)


def test_text_is_stripped(product):
    product["brand"] = "  Dyna-Gro  "
    assert ProductCreate.model_validate(product).brand == "Dyna-Gro"


@pytest.mark.parametrize("field", ["brand", "name", "type", "label_directions"])
def test_required_field_missing_rejected(product, field):
    del product[field]
    rejects(product)


def test_notes_default_to_empty(product):
    del product["notes"]
    assert ProductCreate.model_validate(product).notes == ""


def test_unknown_type_rejected(product):
    product["type"] = "slow_release"
    rejects(product)


# --- npk is required for fertilizers (cross-field rule)


@pytest.mark.parametrize("fertilizer_type", ["liquid_fertilizer", "soluble_powder"])
def test_fertilizer_without_npk_rejected(product, fertilizer_type):
    product["type"] = fertilizer_type
    del product["npk"]
    rejects(product)


def test_additive_without_npk_accepted(product):
    product["type"] = "additive"
    del product["npk"]
    assert ProductCreate.model_validate(product).npk is None


def test_additive_with_npk_accepted(product):
    product["type"] = "additive"
    ProductCreate.model_validate(product)


# --- Npk: validated on its own, so no product-level rule can reject it instead


NUTRIENTS = ["n", "p", "k"]


@pytest.mark.parametrize("value", [0, 100])
@pytest.mark.parametrize("nutrient", NUTRIENTS)
def test_npk_accepts_range_boundaries(nutrient, value):
    Npk.model_validate(VALID_NPK | {nutrient: value})


@pytest.mark.parametrize("value", [-0.01, 100.01])
@pytest.mark.parametrize("nutrient", NUTRIENTS)
def test_npk_rejects_out_of_range(nutrient, value):
    with pytest.raises(ValidationError):
        Npk.model_validate(VALID_NPK | {nutrient: value})


def test_npk_accepts_two_decimal_places():
    Npk.model_validate(VALID_NPK | {"n": 0.25})


def test_npk_rejects_three_decimal_places():
    with pytest.raises(ValidationError):
        Npk.model_validate(VALID_NPK | {"n": 0.125})


def test_npk_rejects_non_number():
    with pytest.raises(ValidationError):
        Npk.model_validate(VALID_NPK | {"n": "nine"})


# Regression: with float, these values lose exactness (0.2 + 83.9 + 15.9 is
# slightly above 100). Decimal keeps each value exactly as printed.
def test_npk_keeps_values_exact():
    npk = Npk.model_validate(VALID_NPK | {"n": 0.2, "p": 83.9, "k": 15.9})
    assert (npk.n, npk.p, npk.k) == (Decimal("0.2"), Decimal("83.9"), Decimal("15.9"))
    assert npk.n + npk.p + npk.k == 100


# P and K may be oxide equivalents, so the total is deliberately not checked.
def test_npk_total_over_100_accepted():
    Npk.model_validate(VALID_NPK | {"n": 82, "p": 30, "k": 10})


@pytest.mark.parametrize("basis", ["oxide", "elemental"])
def test_npk_accepts_each_basis(basis):
    assert Npk.model_validate(VALID_NPK | {"basis": basis}).basis == basis


def test_npk_basis_is_required():
    data = dict(VALID_NPK)
    del data["basis"]
    with pytest.raises(ValidationError):
        Npk.model_validate(data)


def test_npk_rejects_unknown_basis():
    with pytest.raises(ValidationError):
        Npk.model_validate(VALID_NPK | {"basis": "metric"})


# --- LabelDirection


def test_label_directions_cannot_be_empty(product):
    product["label_directions"] = []
    rejects(product)


@pytest.mark.parametrize("bad", [0, -1])
@pytest.mark.parametrize("field", ["amount", "water_volume"])
def test_amount_must_be_positive(product, field, bad):
    product["label_directions"][0][field] = bad
    rejects(product)


@pytest.mark.parametrize("field", ["amount", "water_volume"])
def test_small_positive_amount_accepted(product, field):
    product["label_directions"][0][field] = 0.01
    ProductCreate.model_validate(product)


@pytest.mark.parametrize("unit", ["ml", "g", "tsp", "tbsp"])
def test_amount_unit_accepts_each_unit(product, unit):
    product["label_directions"][0]["amount_unit"] = unit
    ProductCreate.model_validate(product)


@pytest.mark.parametrize("unit", ["L", "gal"])
def test_water_unit_accepts_each_unit(product, unit):
    product["label_directions"][0]["water_unit"] = unit
    ProductCreate.model_validate(product)


@pytest.mark.parametrize(
    "field, bad_unit", [("amount_unit", "cup"), ("water_unit", "ml")]
)
def test_unknown_unit_rejected(product, field, bad_unit):
    product["label_directions"][0][field] = bad_unit
    rejects(product)


# --- LabelFrequency: "kind" picks the model


frequency = TypeAdapter(LabelFrequency)


def test_interval_accepts_one_day():
    assert frequency.validate_python({"kind": "interval", "days": 1}).days == 1


@pytest.mark.parametrize("bad_days", [0, -1, 1.5])
def test_interval_rejects_bad_days(bad_days):
    with pytest.raises(ValidationError):
        frequency.validate_python({"kind": "interval", "days": bad_days})


def test_interval_requires_days():
    with pytest.raises(ValidationError):
        frequency.validate_python({"kind": "interval"})


def test_every_watering_rejects_days():
    with pytest.raises(ValidationError):
        frequency.validate_python({"kind": "every_watering", "days": 7})


@pytest.mark.parametrize("bad_kind", ["monthly", "Interval", None])
def test_unknown_kind_rejected(bad_kind):
    with pytest.raises(ValidationError):
        frequency.validate_python({"kind": bad_kind, "days": 7})


def test_kind_is_required():
    with pytest.raises(ValidationError):
        frequency.validate_python({"days": 7})


# --- use: needed to tell several directions apart


def test_single_direction_needs_no_use(product):
    product["label_directions"] = product["label_directions"][:1]
    del product["label_directions"][0]["use"]
    assert ProductCreate.model_validate(product).label_directions[0].use is None


def test_several_directions_each_need_a_use(product):
    del product["label_directions"][1]["use"]
    rejects(product)


@pytest.mark.parametrize(
    "first, second",
    [
        ("maintenance", "maintenance"),
        ("Maintenance", "maintenance"),
        ("maintenance ", "maintenance"),
    ],
    ids=["same", "different-case", "extra-space"],
)
def test_several_directions_reject_duplicate_use(product, first, second):
    product["label_directions"][0]["use"] = first
    product["label_directions"][1]["use"] = second
    rejects(product)


@pytest.mark.parametrize("blank", ["", "   "])
def test_use_rejects_blank(product, blank):
    product["label_directions"] = product["label_directions"][:1]
    product["label_directions"][0]["use"] = blank
    rejects(product)


# --- unknown fields are rejected at every level


@pytest.mark.parametrize(
    "path",
    [
        ("unknown_field",),
        ("npk", "unknown_field"),
        ("label_directions", 0, "note"),  # the old name of "use"
        ("label_directions", 1, "frequency", "unknown_field"),
    ],
)
def test_unknown_field_rejected(product, path):
    set_field(product, path, "typo or stale field")
    rejects(product)

