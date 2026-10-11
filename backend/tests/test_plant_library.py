import json
from pathlib import Path

import pytest

from app.schemas import PlantCareGuide

PLANTS_DIR = Path(__file__).parent.parent / "data" / "plants"
PLANT_FILES = sorted(PLANTS_DIR.glob("*.json"))


def test_library_is_not_empty():
    assert PLANT_FILES


@pytest.mark.parametrize("path", PLANT_FILES, ids=lambda p: p.stem)
def test_plant_file_matches_schema(path):
    PlantCareGuide.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", PLANT_FILES, ids=lambda p: p.stem)
def test_file_name_matches_id(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert path.stem == data["id"]
