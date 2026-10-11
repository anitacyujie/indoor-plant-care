import copy

import pytest
from pydantic import ValidationError

from app.schemas import MAX_LUX, PlantCareGuide

VALID_GUIDE = {
    "id": "monstera-deliciosa-albo",
    "names": {"zh": "白锦龟背竹", "en": "Monstera Albo"},
    "scientific_name": "Monstera deliciosa",
    "cultivar": "Albo Borsigiana",
    "variegated": True,
    "light": {
        "ideal_lux": {"min": 10000, "max": 20000},
        "tolerable_lux": {"min": 5000, "max": 30000},
        "lux_basis": "converted_from_label",
    },
    "watering": {
        "interval_days": {"spring_summer": 7, "fall_winter": 14},
        "how_to_check": "Water when the top few cm of soil are dry.",
    },
    "soil": {"mix": [{"component": "bark", "parts": 1}]},
    "fertilizer": {
        "npk_ratio": "3-1-2",
        "dilution": "half strength",
        "frequency_days": 30,
    },
    "sources": [{"title": "Example", "url": "https://example.com"}],
}


@pytest.fixture
def guide():
    return copy.deepcopy(VALID_GUIDE)


def test_valid_guide_passes(guide):
    result = PlantCareGuide.model_validate(guide)
    assert result.id == "monstera-deliciosa-albo"


def test_watering_interval_must_be_positive(guide):
    guide["watering"]["interval_days"]["spring_summer"] = 0
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def set_field(data, path, value):
    *parents, last = path
    for key in parents:
        data = data[key]
    data[last] = value


REQUIRED_TEXT_FIELDS = [
    ("names", "zh"),
    ("names", "en"),
    ("scientific_name",),
    ("watering", "how_to_check"),
    ("soil", "mix", 0, "component"),
    ("fertilizer", "npk_ratio"),
    ("fertilizer", "dilution"),
    ("sources", 0, "title"),
]


@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("path", REQUIRED_TEXT_FIELDS)
def test_required_text_rejects_blank(guide, path, blank):
    set_field(guide, path, blank)
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_sources_must_not_be_empty(guide):
    guide["sources"] = []
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


@pytest.mark.parametrize(
    "bad_url", ["not-a-url", "", "example.com", "ftp://example.com"]
)
def test_source_url_rejects_invalid(guide, bad_url):
    guide["sources"][0]["url"] = bad_url
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


@pytest.mark.parametrize(
    "good_url", ["https://example.com", "http://example.com/page?id=1"]
)
def test_source_url_accepts_valid(guide, good_url):
    guide["sources"][0]["url"] = good_url
    PlantCareGuide.model_validate(guide)


LUX_RANGES = ["ideal_lux", "tolerable_lux"]


@pytest.mark.parametrize("lux_range", LUX_RANGES)
def test_lux_max_below_min_rejected(guide, lux_range):
    guide["light"][lux_range] = {"min": 20000, "max": 10000}
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_lux_max_equal_to_min_accepted(guide):
    guide["light"]["ideal_lux"] = {"min": 10000, "max": 10000}
    guide["light"]["tolerable_lux"] = {"min": 10000, "max": 10000}
    PlantCareGuide.model_validate(guide)


@pytest.mark.parametrize("lux_range", LUX_RANGES)
def test_lux_max_is_required(guide, lux_range):
    del guide["light"][lux_range]["max"]
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


# Each bad range breaks only the 0..MAX_LUX bound, never the max >= min rule.
@pytest.mark.parametrize(
    "bad_range",
    [
        {"min": -1, "max": 20000},
        {"min": 10000, "max": MAX_LUX + 1},
    ],
)
@pytest.mark.parametrize("lux_range", LUX_RANGES)
def test_lux_rejects_out_of_range(guide, lux_range, bad_range):
    guide["light"][lux_range] = bad_range
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_lux_accepts_full_range_boundaries(guide):
    guide["light"]["ideal_lux"] = {"min": 0, "max": MAX_LUX}
    guide["light"]["tolerable_lux"] = {"min": 0, "max": MAX_LUX}
    PlantCareGuide.model_validate(guide)


# Fixture tolerable_lux is 5000..30000; each ideal range is valid on its own.
@pytest.mark.parametrize(
    "ideal",
    [
        {"min": 4000, "max": 20000},
        {"min": 10000, "max": 31000},
    ],
)
def test_ideal_lux_outside_tolerable_rejected(guide, ideal):
    guide["light"]["ideal_lux"] = ideal
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)
