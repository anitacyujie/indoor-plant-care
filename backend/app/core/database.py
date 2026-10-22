import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session

DEFAULT_DB_PATH = Path(__file__).parents[2] / "plant_care.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")


class Base(DeclarativeBase):
    """Parent class of all table models; collects their table definitions."""


def create_db_engine(url: str, **options) -> Engine:
    """Create an engine that enforces foreign keys on every SQLite connection.

    SQLite ignores REFERENCES and ON DELETE CASCADE unless this pragma is
    switched on, and it must be set again for each new connection.
    options are passed to create_engine (tests use them for a shared
    in-memory database).
    """
    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


engine = create_db_engine(DATABASE_URL)


def get_session() -> Iterator[Session]:
    """A FastAPI dependency: one session per request, closed when it ends.

    Tests override this dependency to use a separate database.
    """
    with Session(engine) as session:
        yield session
