"""Products as the API accepts and returns them."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, PlainSerializer, model_validator

from app.core.schemas import Days, NonEmptyStr, StrictModel, decimal_to_json_number


# Decimal, not float, so values stay exactly as printed (0.2 stays 0.2) and
# later math on them has no binary rounding error. In JSON it is a number:
# with at most 2 decimal places up to 100, float shows each value exactly.
Percent = Annotated[
    Decimal,
    Field(ge=0, le=100, decimal_places=2),
    PlainSerializer(decimal_to_json_number, when_used="json"),
]

# How P and K are printed. The US and Canada use oxides (P2O5, K2O); the EU
# defaults to oxides but allows elements; Australia uses elements (P, K).
NpkBasis = Literal["oxide", "elemental"]


class Npk(StrictModel):
    """NPK as printed on the label, in percent, e.g. 9-3-6.

    Each number is a percent of the product, but P and K may be oxide
    equivalents, so the three do not add up to a share of the product and
    their total is not checked.
    """

    n: Percent
    p: Percent
    k: Percent
    basis: NpkBasis  # no default: a wrong guess would silently mislabel the data


class IntervalFrequency(StrictModel):
    kind: Literal["interval"]
    days: Days


class EveryWateringFrequency(StrictModel):
    kind: Literal["every_watering"]


class AsNeededFrequency(StrictModel):
    """No fixed schedule, e.g. a leaf spray for deficient plants."""

    kind: Literal["as_needed"]


# "kind" decides which model validates the rest, like a sealed interface.
LabelFrequency = Annotated[
    IntervalFrequency | EveryWateringFrequency | AsNeededFrequency,
    Field(discriminator="kind"),
]

PositiveAmount = Annotated[float, Field(gt=0)]

# How a direction is applied: watering plants in soil, feeding a hydroponic
# (or semi-hydro) reservoir, or spraying the leaves. A care plan picks the
# directions that fit its group's growing medium by this field.
Application = Literal["soil", "hydroponic", "foliar"]


class LabelDirection(StrictModel):
    """One dose and how often to apply it, in the units printed on the label.

    Labels often give several, e.g. 1/4 tsp per gallon every watering, or
    1 tsp per gallon monthly, so dose and frequency are kept together.
    """

    application: Application
    amount: PositiveAmount
    amount_unit: Literal["ml", "g", "tsp", "tbsp"]
    water_volume: PositiveAmount
    water_unit: Literal["L", "gal"]
    frequency: LabelFrequency
    # What this direction is for, as printed, e.g. "maintenance".
    use: NonEmptyStr | None = None

    @model_validator(mode="after")
    def check_foliar_is_not_every_watering(self) -> Self:
        # A leaf spray is not part of watering.
        if self.application == "foliar" and self.frequency.kind == "every_watering":
            raise ValueError("a foliar direction cannot be every watering")
        return self


ProductType = Literal["liquid_fertilizer", "soluble_powder", "additive"]


class ProductCreate(StrictModel):
    """A care product as entered from its label."""

    brand: NonEmptyStr
    name: NonEmptyStr
    type: ProductType
    npk: Npk | None = None
    label_directions: list[LabelDirection] = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def check_fertilizer_has_npk(self) -> Self:
        if self.type != "additive" and self.npk is None:
            raise ValueError("fertilizers must state their NPK")
        return self

    @model_validator(mode="after")
    def check_several_directions_are_named(self) -> Self:
        """With several directions for one application, each needs a distinct use.

        Directions for different applications are told apart by the
        application, so one soil and one hydroponic direction need no use.
        """
        uses_by_application: dict[str, list[str | None]] = {}
        for direction in self.label_directions:
            uses_by_application.setdefault(direction.application, []).append(direction.use)
        for application, uses in uses_by_application.items():
            if len(uses) < 2:
                continue
            if None in uses:
                raise ValueError(
                    f"each {application} direction needs a use when there are several"
                )
            # casefold: "Maintenance" and "maintenance" are the same use.
            if len({use.casefold() for use in uses}) != len(uses):
                raise ValueError(f"{application} direction uses must be unique")
        return self


class ProductRead(ProductCreate):
    """A saved product, as the API returns it."""

    id: int
    created_at: datetime
