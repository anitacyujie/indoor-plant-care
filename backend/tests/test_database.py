import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import database


@pytest.fixture(autouse=True)
def memory_engine(monkeypatch):
    """Point the app engine at an in-memory database, so no file is created."""
    engine = database.create_db_engine("sqlite://")
    monkeypatch.setattr(database, "engine", engine)
    yield engine
    engine.dispose()


def test_get_session_uses_app_engine(memory_engine):
    sessions = database.get_session()
    session = next(sessions)
    assert isinstance(session, Session)
    assert session.get_bind() is memory_engine
    sessions.close()


def test_get_session_closes_session_when_request_ends():
    sessions = database.get_session()
    session = next(sessions)
    session.execute(text("SELECT 1"))  # starts a transaction
    assert session.in_transaction()

    sessions.close()  # what FastAPI does after the response is sent

    assert not session.in_transaction()
