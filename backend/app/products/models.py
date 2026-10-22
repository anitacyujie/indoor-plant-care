"""Product tables."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.columns import HundredthsDecimal, UtcDateTime, utc_now
from app.core.database import Base


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

    # In label order. delete-orphan: removing a direction from this list
    # deletes its row. passive_deletes: when a product is deleted, leave its
    # directions to ON DELETE CASCADE instead of deleting each from Python.
    label_directions: Mapped[list["ProductLabelDirection"]] = relationship(
        back_populates="product",
        order_by="ProductLabelDirection.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# One row per product, ignoring case: "Dyna-Gro Foliage-Pro" and
# "dyna-gro foliage-pro" are the same product entered twice.
Index(
    "uq_products_brand_name",
    func.lower(Product.brand),
    func.lower(Product.name),
    unique=True,
)


class ProductLabelDirection(Base):
    """One dose and frequency from a product's label, in the label's units."""

    __tablename__ = "product_label_directions"
    __table_args__ = (
        UniqueConstraint("product_id", "position", name="uq_direction_position"),
        CheckConstraint("position >= 0", name="position_not_negative"),
        CheckConstraint(
            "application IN ('soil', 'hydroponic', 'foliar')", name="valid_application"
        ),
        CheckConstraint(
            "application <> 'foliar' OR frequency_kind <> 'every_watering'",
            name="foliar_not_every_watering",
        ),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("amount_unit IN ('ml', 'g', 'tsp', 'tbsp')", name="valid_amount_unit"),
        CheckConstraint("water_volume > 0", name="water_volume_positive"),
        CheckConstraint("water_unit IN ('L', 'gal')", name="valid_water_unit"),
        # The discriminated union in table form: days only for "interval".
        # IS NOT NULL is needed: NULL > 0 is NULL, and a CHECK only rejects FALSE.
        CheckConstraint(
            "(frequency_kind = 'interval' AND frequency_days IS NOT NULL AND frequency_days > 0)"
            " OR (frequency_kind IN ('every_watering', 'as_needed') AND frequency_days IS NULL)",
            name="valid_frequency",
        ),
        CheckConstraint("use IS NULL OR length(trim(use)) > 0", name="use_not_blank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]  # order on the label; a table has no order of its own
    application: Mapped[str]
    amount: Mapped[float]
    amount_unit: Mapped[str]
    water_volume: Mapped[float]
    water_unit: Mapped[str]
    frequency_kind: Mapped[str]
    frequency_days: Mapped[int | None]
    # "Several directions for one application each need a use" spans rows,
    # which a CHECK cannot see; Pydantic enforces it.
    use: Mapped[str | None]

    product: Mapped[Product] = relationship(back_populates="label_directions")


# A use is unique within a product's application, ignoring case: a soil and a
# hydroponic direction may both be "maintenance". NULLs never collide, so
# several unnamed directions are allowed here.
Index(
    "uq_direction_use",
    ProductLabelDirection.product_id,
    ProductLabelDirection.application,
    func.lower(ProductLabelDirection.use),
    unique=True,
)
