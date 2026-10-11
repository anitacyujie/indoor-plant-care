import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import TypeAdapter

from app.schemas import (
    WateringCheck,
    WateringCheckId,
    WindowExposure,
    WindowExposureId,
)

DATA_DIR = Path(__file__).parent.parent / "data"

# Shared reference data: (file, model for each entry, literal its ids must match)
REFERENCE_FILES = [
    ("window_exposures.json", WindowExposure, WindowExposureId),
    ("watering_checks.json", WateringCheck, WateringCheckId),
]


@pytest.mark.parametrize(
    "file_name, model, id_literal",
    REFERENCE_FILES,
    ids=[file_name for file_name, _, _ in REFERENCE_FILES],
)
def test_ids_match_schema_literal(file_name, model, id_literal):
    raw = json.loads((DATA_DIR / file_name).read_text(encoding="utf-8"))
    entries = TypeAdapter(list[model]).validate_python(raw)
    ids = [entry.id for entry in entries]
    assert sorted(ids) == sorted(get_args(id_literal))
