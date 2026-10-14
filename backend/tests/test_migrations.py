from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

import app.models  # noqa: F401  registers every table on Base.metadata
from app import database
from app.database import Base, create_db_engine

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


def test_downgrade_removes_all_tables(engine, alembic_config):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
