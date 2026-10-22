from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

import app.all_models  # noqa: F401  registers every table on Base.metadata
from app.core import database
from app.core.database import Base, create_db_engine

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """An engine on an empty database file that migrations/env.py will target."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr(database, "DATABASE_URL", url)
    engine = create_db_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def alembic_config():
    # Built in code rather than from alembic.ini, so env.py skips the ini's
    # logging setup, which would replace pytest's log capture.
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def test_migrations_match_models(engine, alembic_config):
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def checks_and_indexes(engine: Engine) -> tuple[dict, dict]:
    """CHECK constraints and index definitions, with whitespace normalized.

    compare_metadata skips both on SQLite, so they are compared directly.
    """
    inspector = inspect(engine)
    checks = {
        (table, check["name"]): " ".join(check["sqltext"].split())
        for table in inspector.get_table_names()
        for check in inspector.get_check_constraints(table)
    }
    with engine.connect() as connection:
        rows = connection.execute(
            # sql is NULL for indexes SQLite creates itself (e.g. for PRIMARY KEY)
            text("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
        )
        indexes = {name: " ".join(sql.split()) for name, sql in rows}
    return checks, indexes


def test_migrations_match_models_checks_and_indexes(engine, alembic_config):
    command.upgrade(alembic_config, "head")
    model_engine = create_db_engine("sqlite://")
    Base.metadata.create_all(model_engine)
    try:
        assert checks_and_indexes(engine) == checks_and_indexes(model_engine)
    finally:
        model_engine.dispose()


def test_downgrade_removes_all_tables(engine, alembic_config):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
