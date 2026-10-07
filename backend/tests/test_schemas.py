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