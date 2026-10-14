"""Database tables for user data. The plant library stays in JSON files."""

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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
