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


# "kind" decides which model validates the rest, like a sealed interface.
LabelFrequency = Annotated[
    IntervalFrequency | EveryWateringFrequency, Field(discriminator="kind")
]

PositiveAmount = Annotated[float, Field(gt=0)]


class LabelDirection(StrictModel):
    """One dose and how often to apply it, in the units printed on the label.

    Labels often give several, e.g. 1/4 tsp per gallon every watering, or
    1 tsp per gallon monthly, so dose and frequency are kept together.
    """

    amount: PositiveAmount
    amount_unit: Literal["ml", "g", "tsp", "tbsp"]
    water_volume: PositiveAmount
    water_unit: Literal["L", "gal"]
    frequency: LabelFrequency
    # What this direction is for, as printed, e.g. "maintenance".
    use: NonEmptyStr | None = None


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
        """With several directions, each needs a distinct use to choose by."""
        if len(self.label_directions) < 2:
            return self
        uses = [direction.use for direction in self.label_directions]
        if None in uses:
            raise ValueError("each label direction needs a use when there are several")
        # casefold: "Maintenance" and "maintenance" are the same use.
        if len({use.casefold() for use in uses}) != len(uses):
            raise ValueError("label direction uses must be unique")
        return self


class ProductRead(ProductCreate):
    """A saved product, as the API returns it."""

    id: int
    created_at: datetime
