"""Database tables and the column types they share."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, TypeDecorator


class UtcDateTime(TypeDecorator):
    """A datetime column that always holds UTC.

    SQLite drops the time zone, so values are converted to UTC on the way in
    and marked as UTC on the way out. Naive datetimes are rejected, because
    nothing could tell which time zone they meant.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


class HundredthsDecimal(TypeDecorator):
    """A Decimal with at most 2 decimal places, stored exactly as hundredths.

    SQLite has no exact decimal type (NUMERIC is stored as floating point),
    so 9.25 is stored as the integer 925 and read back as Decimal("9.25").
    Floats are rejected, because they may already carry rounding error.
    """

    impl = Integer
    cache_ok = True

    def process_bind_param(self, value: Decimal | int | None, dialect) -> int | None:
        if value is None:
            return None
        if isinstance(value, float):
            raise TypeError("use Decimal, not float")
        hundredths = Decimal(value) * 100
        if hundredths != hundredths.to_integral_value():
            raise ValueError("at most 2 decimal places")
        return int(hundredths)

    def process_result_value(self, value: int | None, dialect) -> Decimal | None:
        return None if value is None else Decimal(value) / 100
