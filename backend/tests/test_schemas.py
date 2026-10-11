import copy

import pytest
from pydantic import ValidationError

from app.schemas import MAX_PPFD, MAX_WINDOW_DISTANCE_M, PlantCareGuide, Source

VALID_GUIDE = {
    "id": "monstera-deliciosa-albo",
    "names": {"zh": "白锦龟背竹", "en": "Monstera Albo"},
    "scientific_name": "Monstera deliciosa",
    "cultivar": "Albo Borsigiana",
    "variegated": True,
    "light": {
        "ideal_ppfd": {"min": 150, "max": 250},
        "tolerable_ppfd": {"min": 100, "max": 400},
        "ppfd_basis": "converted_from_label",
        "placement": [
            {"window": "gentle", "distance_m": {"min": 0, "max": 1}},
            {"window": "strong", "distance_m": {"min": 0.6, "max": 1.2}},
        ],
        "source_ids": ["example"],
    },
    "watering": {
        "interval_days": {"spring_summer": 7, "fall_winter": 14},
        "how_to_check": "Water when the top few cm of soil are dry.",
        "how_to_water": "Water thoroughly, then empty the saucer.",
        "source_ids": ["example"],
    },
    "soil": {
        "mixes": [
            {
                "watering_style": "top",
                "components": [{"component": "bark", "parts": 1}],
            },
            {
                "watering_style": "bottom",
                "components": [{"component": "coco coir", "parts": 2}],
            },
        ],
        "source_ids": ["example"],
    },
    "fertilizer": {
        "npk_ratio": "3-1-2",
        "dilution": "half strength",
        "frequency_days": 30,
        "source_ids": ["example"],
    },
    "sources": [{"id": "example", "title": "Example", "url": "https://example.com"}],
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
    ("watering", "how_to_water"),
    ("soil", "mixes", 0, "components", 0, "component"),
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


PPFD_RANGES = ["ideal_ppfd", "tolerable_ppfd"]


@pytest.mark.parametrize("ppfd_range", PPFD_RANGES)
def test_ppfd_max_below_min_rejected(guide, ppfd_range):
    guide["light"][ppfd_range] = {"min": 250, "max": 150}
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_ppfd_max_equal_to_min_accepted(guide):
    guide["light"]["ideal_ppfd"] = {"min": 200, "max": 200}
    guide["light"]["tolerable_ppfd"] = {"min": 200, "max": 200}
    PlantCareGuide.model_validate(guide)


@pytest.mark.parametrize("ppfd_range", PPFD_RANGES)
def test_ppfd_max_is_required(guide, ppfd_range):
    del guide["light"][ppfd_range]["max"]
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


# Each bad range breaks only the 0..MAX_PPFD bound. Both ranges get the same
# value so neither max >= min nor ideal-within-tolerable can reject it instead.
@pytest.mark.parametrize(
    "bad_range",
    [
        {"min": -1, "max": 250},
        {"min": 150, "max": MAX_PPFD + 1},
    ],
)
def test_ppfd_rejects_out_of_range(guide, bad_range):
    guide["light"]["ideal_ppfd"] = bad_range
    guide["light"]["tolerable_ppfd"] = bad_range
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_ppfd_accepts_full_range_boundaries(guide):
    guide["light"]["ideal_ppfd"] = {"min": 0, "max": MAX_PPFD}
    guide["light"]["tolerable_ppfd"] = {"min": 0, "max": MAX_PPFD}
    PlantCareGuide.model_validate(guide)


# Fixture tolerable_ppfd is 100..400; each ideal range is valid on its own.
@pytest.mark.parametrize(
    "ideal",
    [
        {"min": 90, "max": 250},
        {"min": 150, "max": 410},
    ],
)
def test_ideal_ppfd_outside_tolerable_rejected(guide, ideal):
    guide["light"]["ideal_ppfd"] = ideal
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


CITING_SECTIONS = ["light", "watering", "soil", "fertilizer"]


@pytest.mark.parametrize("section", CITING_SECTIONS)
def test_section_must_cite_a_source(guide, section):
    guide[section]["source_ids"] = []
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


@pytest.mark.parametrize("section", CITING_SECTIONS)
def test_section_rejects_unknown_source_id(guide, section):
    guide[section]["source_ids"] = ["missing-source"]
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_source_ids_must_be_unique(guide):
    guide["sources"].append(copy.deepcopy(guide["sources"][0]))
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


# Validated on Source alone, so the citation check cannot reject it instead.
def test_source_id_must_be_slug():
    with pytest.raises(ValidationError):
        Source.model_validate(
            {"id": "Not A Slug", "title": "Example", "url": "https://example.com"}
        )


def test_placement_is_required(guide):
    guide["light"]["placement"] = []
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_placement_rejects_unknown_window(guide):
    guide["light"]["placement"][0]["window"] = "partial"
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_placement_rejects_duplicate_window(guide):
    guide["light"]["placement"][1]["window"] = "gentle"
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_distance_max_below_min_rejected(guide):
    guide["light"]["placement"][0]["distance_m"] = {"min": 1.2, "max": 0.6}
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


@pytest.mark.parametrize(
    "bad_distance",
    [
        {"min": -0.1, "max": 1},
        {"min": 0.6, "max": MAX_WINDOW_DISTANCE_M + 0.1},
    ],
)
def test_distance_rejects_out_of_range(guide, bad_distance):
    guide["light"]["placement"][0]["distance_m"] = bad_distance
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_distance_accepts_full_range_boundaries(guide):
    guide["light"]["placement"][0]["distance_m"] = {
        "min": 0,
        "max": MAX_WINDOW_DISTANCE_M,
    }
    PlantCareGuide.model_validate(guide)


@pytest.mark.parametrize(
    "path",
    [
        ("unknown_field",),
        ("light", "note"),
        ("light", "placement", 0, "note"),
        ("sources", 0, "author"),
    ],
)
def test_unknown_field_rejected(guide, path):
    set_field(guide, path, "typo or stale field")
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_soil_mixes_required(guide):
    guide["soil"]["mixes"] = []
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_soil_mix_components_required(guide):
    guide["soil"]["mixes"][0]["components"] = []
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_soil_mix_rejects_unknown_watering_style(guide):
    guide["soil"]["mixes"][0]["watering_style"] = "wick"
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)


def test_soil_mix_rejects_duplicate_watering_style(guide):
    guide["soil"]["mixes"][1]["watering_style"] = "top"
    with pytest.raises(ValidationError):
        PlantCareGuide.model_validate(guide)
