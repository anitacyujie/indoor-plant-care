from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.database import create_db_engine
from app.models import UtcDateTime


def test_foreign_keys_are_enforced(session):
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


class ScratchBase(DeclarativeBase):
    """Separate from the app's Base, so this table never reaches migrations."""


class Stamp(ScratchBase):
    """A test-only table, so UtcDateTime is tested apart from any app table."""

    __tablename__ = "stamps"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UtcDateTime)


@pytest.fixture
def scratch_session():
    engine = create_db_engine("sqlite://")
    ScratchBase.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_datetime_is_read_back_in_utc(scratch_session):
    toronto_winter = timezone(timedelta(hours=-5))
    created = datetime(2026, 1, 15, 23, 30, tzinfo=toronto_winter)
    stamp = Stamp(at=created)
    scratch_session.add(stamp)
    scratch_session.commit()
    scratch_session.expire_all()  # force a fresh read from the database
    assert stamp.at == created
    assert stamp.at.tzinfo == UTC
    assert stamp.at.day == 16  # 23:30 in Toronto is the next day in UTC


def test_datetime_without_time_zone_is_rejected(scratch_session):
    scratch_session.add(Stamp(at=datetime(2026, 1, 15)))
    with pytest.raises(StatementError, match="timezone-aware"):
        scratch_session.commit()
