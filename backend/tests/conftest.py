"""Fixtures shared by all test modules (pytest loads this file automatically)."""

import copy

import pytest
from sqlalchemy.orm import Session

from app.database import Base, create_db_engine

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
        "how_to_check": ["pot_weight"],
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
        "frequency_days": {"spring_summer": 14, "fall_winter": None},
        "source_ids": ["example"],
    },
    "sources": [{"id": "example", "title": "Example", "url": "https://example.com"}],
}


@pytest.fixture
def guide():
    return copy.deepcopy(VALID_GUIDE)


@pytest.fixture
def session():
    """A fresh in-memory database with all tables, discarded after each test."""
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
