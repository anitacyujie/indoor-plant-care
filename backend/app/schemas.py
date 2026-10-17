from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class StrictModel(BaseModel):
    """Base for all schemas: unknown fields (e.g. typos) are errors, not ignored."""

    model_config = ConfigDict(extra="forbid")


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Lowercase words joined by hyphens, e.g. "monstera-deliciosa".
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]

Days = Annotated[int, Field(gt=0)]


# Fixed ids, so the same material is always spelled the same way and can
# later carry reference data (drainage, aeration, ...).
SoilComponentId = Literal[
    "bark",
    "perlite",
    "pumice",
    "coco_coir",
    "peat",
    "sphagnum_moss",
    "charcoal",
    "worm_castings",
    "leca",
    "lava_rock",
    "akadama",
    "potting_soil",
]

# Parts of a mix, e.g. 2 bark : 1 perlite. Shares are computed from parts.
Parts = Annotated[int, Field(gt=0)]


class ListedSoilComponent(StrictModel):
    component: SoilComponentId
    parts: Parts


class OtherSoilComponent(StrictModel):
    """A material not in the list, named by the user."""

    component: Literal["other"]
    name: NonEmptyStr
    parts: Parts


# "component" decides which model applies; only "other" takes a name.
SoilComponent = Annotated[
    ListedSoilComponent | OtherSoilComponent, Field(discriminator="component")
]


# Decimal, not float, so values stay exactly as printed (0.2 stays 0.2) and
# later math on them has no binary rounding error.
Percent = Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]

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
