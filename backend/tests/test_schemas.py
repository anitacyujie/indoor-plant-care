import copy

import pytest
from pydantic import ValidationError

from app.schemas import PlantCareGuide

VALID_GUIDE = {
    "id": "monstera-deliciosa-albo",
    "names": {"zh": "白锦龟背竹", "en": "Monstera Albo"},
    "scientific_name": "Monstera deliciosa",
    "cultivar": "Albo Borsigiana",
    "variegated": True,
    "light": {
        "ideal_lux": {"min": 10000, "max": 20000},
        "minimum_lux": 5000,
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