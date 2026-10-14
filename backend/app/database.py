import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase

DEFAULT_DB_PATH = Path(__file__).parent.parent / "plant_care.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")


class Base(DeclarativeBase):
    """Parent class of all table models; collects their table definitions."""


def create_db_engine(url: str) -> Engine:
    """Create an engine that enforces foreign keys on every SQLite connection.

    SQLite ignores REFERENCES and ON DELETE CASCADE unless this pragma is
    switched on, and it must be set again for each new connection.
    """
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


engine = create_db_engine(DATABASE_URL)
