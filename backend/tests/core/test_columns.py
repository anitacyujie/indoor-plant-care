from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core.database import create_db_engine
from app.core.columns import HundredthsDecimal, UtcDateTime


def test_foreign_keys_are_enforced(session):
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


class ScratchBase(DeclarativeBase):
    """Separate from the app's Base, so this table never reaches migrations."""


class Stamp(ScratchBase):
    """A test-only table, so UtcDateTime is tested apart from any app table."""

    __tablename__ = "stamps"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UtcDateTime)


class Measure(ScratchBase):
    """A test-only table for HundredthsDecimal."""

    __tablename__ = "measures"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(HundredthsDecimal)


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


def save_and_reload(session, row):
    session.add(row)
    session.commit()
    session.expire_all()  # force a fresh read from the database
    return row


@pytest.mark.parametrize("value", ["0", "0.01", "0.25", "9", "15.9", "100"])
def test_decimal_round_trips_exactly(scratch_session, value):
    measure = save_and_reload(scratch_session, Measure(value=Decimal(value)))
    assert measure.value == Decimal(value)
    assert isinstance(measure.value, Decimal)


def test_decimal_is_stored_as_integer_hundredths(scratch_session):
    save_and_reload(scratch_session, Measure(value=Decimal("9.25")))
    raw = scratch_session.execute(text("SELECT value, typeof(value) FROM measures")).one()
    assert tuple(raw) == (925, "integer")


def test_decimal_accepts_int(scratch_session):
    assert save_and_reload(scratch_session, Measure(value=9)).value == Decimal("9")


def test_decimal_none_round_trips(scratch_session):
    assert save_and_reload(scratch_session, Measure(value=None)).value is None


def test_decimal_rejects_three_decimal_places(scratch_session):
    scratch_session.add(Measure(value=Decimal("0.125")))
    with pytest.raises(StatementError, match="2 decimal places"):
        scratch_session.commit()


def test_decimal_rejects_float(scratch_session):
    scratch_session.add(Measure(value=0.25))
    with pytest.raises(StatementError, match="not float"):
        scratch_session.commit()
