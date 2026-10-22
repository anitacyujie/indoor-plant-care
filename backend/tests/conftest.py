"""Fixtures shared by all test modules (pytest loads this file automatically)."""

import copy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, create_db_engine, get_session
from app.main import app

# Every value sits well inside its limits (e.g. 9-3-6, far from 0 and 100),
# so a test can break one rule without another rule rejecting the data first.
VALID_PRODUCT = {
    "brand": "Dyna-Gro",
    "name": "Foliage-Pro",
    "type": "liquid_fertilizer",
    "npk": {"n": 9, "p": 3, "k": 6, "basis": "oxide"},
    "label_directions": [
        {
            "application": "soil",
            "amount": 0.25,
            "amount_unit": "tsp",
            "water_volume": 1,
            "water_unit": "gal",
            "frequency": {"kind": "every_watering"},
            "use": "maintenance",
            "details": "",
        },
        {
            "application": "soil",
            "amount": 1,
            "amount_unit": "tsp",
            "water_volume": 1,
            "water_unit": "gal",
            "frequency": {"kind": "interval", "days": 30},
            "use": "monthly feeding",
            "details": "",
        },
    ],
    "notes": "Urea-free.",
}


@pytest.fixture
def product():
    """A fresh copy of VALID_PRODUCT, so one test's changes never leak into another."""
    return copy.deepcopy(VALID_PRODUCT)


# A soil mix with listed components and one "other", so rules for both kinds
# can be tested by changing one entry.
VALID_MEDIUM = {
    "name": "Aroid mix",
    "method": "soil",
    "components": [
        {"component": "bark", "parts": 2},
        {"component": "perlite", "parts": 1},
        {"component": "other", "name": "zeolite", "parts": 1},
    ],
    "notes": "Chunky; dries in about a week.",
}


@pytest.fixture
def medium():
    """A fresh copy of VALID_MEDIUM."""
    return copy.deepcopy(VALID_MEDIUM)


@pytest.fixture
def session():
    """A fresh in-memory database with all tables, discarded after each test."""
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client():
    """A test client whose requests use a fresh in-memory database.

    An in-memory SQLite database exists only on the connection that made it,
    and TestClient handles requests in another thread. StaticPool hands
    every session that one connection, so requests see the tables.
    """
    engine = create_db_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()
