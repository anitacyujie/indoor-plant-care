import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import TypeAdapter

from app.schemas import WindowExposure, WindowExposureId

DATA_FILE = Path(__file__).parent.parent / "data" / "window_exposures.json"


@pytest.fixture
def exposures():
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return TypeAdapter(list[WindowExposure]).validate_python(raw)


def test_file_matches_schema(exposures):
    assert len(exposures) > 0


def test_ids_match_schema_literal(exposures):
    ids = [exposure.id for exposure in exposures]
    assert sorted(ids) == sorted(get_args(WindowExposureId))
