"""Database tables and the column types they share."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, TypeDecorator


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
