"""Growing medium tables."""

from datetime import datetime
from typing import get_args

from sqlalchemy import CheckConstraint, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.columns import UtcDateTime, sql_in_list, utc_now
from app.core.database import Base
from app.growing_media.schemas import GrowingMethod, MediumComponentId


class GrowingMedium(Base):
    """A soil mix or other medium, shared by any number of groups.

    "Soil and semi-hydro need at least one component" spans rows, which a
    CHECK cannot see; Pydantic enforces it.
    """

    __tablename__ = "growing_media"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="medium_name_not_blank"),
        CheckConstraint(f"method IN ({sql_in_list(get_args(GrowingMethod))})", name="valid_method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    method: Mapped[str]
    notes: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    # Same cascade setup as Product.label_directions. Order does not matter
    # in a mix, so there is no position: most parts first, then by name
    # (the other name, or the listed id), ignoring case.
    components: Mapped[list["GrowingMediumComponent"]] = relationship(
        back_populates="medium",
        order_by=lambda: (
            GrowingMediumComponent.parts.desc(),
            func.lower(func.coalesce(GrowingMediumComponent.other_name, GrowingMediumComponent.component)),
        ),
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# One medium per name, ignoring case.
Index("uq_growing_media_name", func.lower(GrowingMedium.name), unique=True)


class GrowingMediumComponent(Base):
    """One material of a medium and its parts, e.g. bark, 2 parts."""

    __tablename__ = "growing_medium_components"
    __table_args__ = (
        CheckConstraint("parts > 0", name="parts_positive"),
        # Built from the schema's list, so the two cannot drift apart. Adding
        # an id needs a migration too (the migration tests catch a missing one).
        CheckConstraint(
            f"component IN ({sql_in_list((*get_args(MediumComponentId), 'other'))})",
            name="valid_component",
        ),
        # A name only for "other", and then not blank. IS NOT NULL: a NULL
        # result would pass the check.
        CheckConstraint(
            "(component = 'other' AND other_name IS NOT NULL AND length(trim(other_name)) > 0)"
            " OR (component <> 'other' AND other_name IS NULL)",
            name="other_name_only_for_other",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    growing_medium_id: Mapped[int] = mapped_column(
        ForeignKey("growing_media.id", ondelete="CASCADE"), index=True
    )
    component: Mapped[str]
    other_name: Mapped[str | None]
    parts: Mapped[int]

    medium: Mapped[GrowingMedium] = relationship(back_populates="components")


# Each listed component once per medium; "other" rows are left to the index
# below, so a medium may have several of them.
Index(
    "uq_medium_listed_component",
    GrowingMediumComponent.growing_medium_id,
    GrowingMediumComponent.component,
    unique=True,
    sqlite_where=text("component <> 'other'"),
    postgresql_where=text("component <> 'other'"),
)

# Each other name once per medium, ignoring case. The schema also treats
# spaces and hyphens as underscores and rejects names of listed components;
# those rules are left to Pydantic.
Index(
    "uq_medium_other_name",
    GrowingMediumComponent.growing_medium_id,
    func.lower(GrowingMediumComponent.other_name),
    unique=True,
)
