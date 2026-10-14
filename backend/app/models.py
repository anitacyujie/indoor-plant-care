"""Database tables for user data. The plant library stays in JSON files."""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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


class UserSettings(Base):
    """Settings needed to compute care dates; one row until we add accounts."""

    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("hemisphere IN ('north', 'south')", name="valid_hemisphere"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    timezone: Mapped[str]  # IANA name, e.g. "America/Toronto", so DST is handled
    hemisphere: Mapped[str]  # decides which months count as spring_summer


class MyPlant(Base):
    """A plant the user owns, pointing at one guide in the plant library."""

    __tablename__ = "my_plants"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Not a foreign key: the library lives in JSON, so the app checks this id.
    plant_id: Mapped[str]
    nickname: Mapped[str]  # not unique: two plants may share a name
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    # passive_deletes: leave deleting the events to ON DELETE CASCADE in the
    # database instead of loading and deleting each one from Python.
    watering_events: Mapped[list["WateringEvent"]] = relationship(
        back_populates="my_plant", passive_deletes=True
    )


class WateringEvent(Base):
    """One watering. The latest one decides when the plant needs water next."""

    __tablename__ = "watering_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    my_plant_id: Mapped[int] = mapped_column(
        ForeignKey("my_plants.id", ondelete="CASCADE"), index=True
    )
    watered_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    my_plant: Mapped[MyPlant] = relationship(back_populates="watering_events")
