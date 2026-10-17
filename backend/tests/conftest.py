"""Fixtures shared by all test modules (pytest loads this file automatically)."""

import copy

import pytest
from sqlalchemy.orm import Session

from app.database import Base, create_db_engine

# Every value sits well inside its limits (e.g. 9-3-6, far from 0 and 100),
# so a test can break one rule without another rule rejecting the data first.
VALID_PRODUCT = {
    "brand": "Dyna-Gro",
    "name": "Foliage-Pro",
    "type": "liquid_fertilizer",
    "npk": {"n": 9, "p": 3, "k": 6, "basis": "oxide"},
    "label_directions": [
        {
            "amount": 0.25,
            "amount_unit": "tsp",
            "water_volume": 1,
            "water_unit": "gal",
            "frequency": {"kind": "every_watering"},
            "use": "maintenance",
        },
        {
            "amount": 1,
            "amount_unit": "tsp",
            "water_volume": 1,
            "water_unit": "gal",
            "frequency": {"kind": "interval", "days": 30},
            "use": "monthly feeding",
        },
    ],
    "notes": "Urea-free.",
}


@pytest.fixture
def product():
    """A fresh copy of VALID_PRODUCT, so one test's changes never leak into another."""
    return copy.deepcopy(VALID_PRODUCT)


@pytest.fixture
def session():
    """A fresh in-memory database with all tables, discarded after each test."""
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
