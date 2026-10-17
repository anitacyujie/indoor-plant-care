"""Database tables and the column types they share."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, TypeDecorator, func
from sqlalchemy.orm import Mapped, mapped_column

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


class Product(Base):
    """A care product as described by its label; shared, not personal data.

    The main rules are also checked in Pydantic, but the database repeats the
    single-row ones so data written by any other path (scripts, imports)
    cannot break them either.
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("length(trim(brand)) > 0", name="brand_not_blank"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "type IN ('liquid_fertilizer', 'soluble_powder', 'additive')",
            name="valid_type",
        ),
        CheckConstraint("npk_basis IN ('oxide', 'elemental')", name="valid_npk_basis"),
        # NPK is all four columns or none (an additive may have no NPK).
        CheckConstraint(
            "(npk_n IS NULL) = (npk_p IS NULL)"
            " AND (npk_n IS NULL) = (npk_k IS NULL)"
            " AND (npk_n IS NULL) = (npk_basis IS NULL)",
            name="npk_all_or_none",
        ),
        # Stored in hundredths, so 0-100 % is 0-10000.
        CheckConstraint(
            "npk_n BETWEEN 0 AND 10000"
            " AND npk_p BETWEEN 0 AND 10000"
            " AND npk_k BETWEEN 0 AND 10000",
            name="npk_in_range",
        ),
        CheckConstraint(
            "type = 'additive' OR npk_n IS NOT NULL", name="fertilizer_has_npk"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str]
    name: Mapped[str]
    type: Mapped[str]
    npk_n: Mapped[Decimal | None] = mapped_column(HundredthsDecimal)
    npk_p: Mapped[Decimal | None] = mapped_column(HundredthsDecimal)
    npk_k: Mapped[Decimal | None] = mapped_column(HundredthsDecimal)
    npk_basis: Mapped[str | None]
    notes: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


# One row per product, ignoring case: "Dyna-Gro Foliage-Pro" and
# "dyna-gro foliage-pro" are the same product entered twice.
Index(
    "uq_products_brand_name",
    func.lower(Product.brand),
    func.lower(Product.name),
    unique=True,
)
