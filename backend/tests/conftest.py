"""Fixtures shared by all test modules (pytest loads this file automatically)."""

import pytest
from sqlalchemy.orm import Session

from app.database import Base, create_db_engine


@pytest.fixture
def session():
    """A fresh in-memory database with all tables, discarded after each test."""
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
