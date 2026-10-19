from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    PlainSerializer,
    StringConstraints,
    model_validator,
)


class StrictModel(BaseModel):
    """Base for all schemas: unknown fields (e.g. typos) are errors, not ignored."""

    model_config = ConfigDict(extra="forbid")


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Lowercase words joined by hyphens, e.g. "monstera-deliciosa".
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]

Days = Annotated[int, Field(gt=0)]


# Materials of a growing medium (soil mixes and semi-hydro media alike).
# Fixed ids, so the same material is always spelled the same way and can
# later carry reference data (drainage, aeration, ...).
MediumComponentId = Literal[
    "bark",
    "perlite",
    "pumice",
    "coco_coir",
    "peat",
    "sphagnum_moss",
    "charcoal",
    "worm_castings",
    "leca",
    "pon",  # a mineral semi-hydro substrate, usually called by this name
    "lava_rock",
    "akadama",
    "potting_soil",
]

# Parts of a medium, e.g. 2 bark : 1 perlite. Shares are computed from parts.
Parts = Annotated[int, Field(gt=0)]


class ListedMediumComponent(StrictModel):
    component: MediumComponentId
    parts: Parts


class OtherMediumComponent(StrictModel):
    """A material not in the list, named by the user."""

    component: Literal["other"]
    name: NonEmptyStr
    parts: Parts


# "component" decides which model applies; only "other" takes a name.
MediumComponent = Annotated[
    ListedMediumComponent | OtherMediumComponent, Field(discriminator="component")
]


# soil: a soil or chunky mix. semi_hydro: an inert medium such as LECA or pon
# over a water reservoir. hydro: plants grown in water.
GrowingMethod = Literal["soil", "semi_hydro", "hydro"]


def normalize_component_name(name: str) -> str:
    """"Coco coir", "coco-coir" and "Coco_Coir" all become "coco_coir"."""
    return name.casefold().replace(" ", "_").replace("-", "_")


class GrowingMediumCreate(StrictModel):
    """A growing medium as entered by the user; shared by any number of groups."""

    name: NonEmptyStr
    method: GrowingMethod
    components: list[MediumComponent] = []
    notes: str = ""

    @model_validator(mode="after")
    def check_components_for_method(self) -> Self:
        # Water culture may be water alone; every other method has a medium.
        if self.method != "hydro" and not self.components:
            raise ValueError(f"a {self.method} medium needs at least one component")
        return self

    @model_validator(mode="after")
    def check_components_unique(self) -> Self:
        listed = [c.component for c in self.components if isinstance(c, ListedMediumComponent)]
        if len(listed) != len(set(listed)):
            raise ValueError("each listed component may appear only once")

        others = [
            normalize_component_name(c.name)
            for c in self.components
            if isinstance(c, OtherMediumComponent)
        ]
        if len(others) != len(set(others)):
            raise ValueError("each other component name may appear only once")
        # An "other" spelled like a listed id would store one material two ways.
        clashes = set(others) & set(get_args(MediumComponentId))
        if clashes:
            raise ValueError(f"use the listed component instead of other: {sorted(clashes)}")
        return self


def decimal_to_json_number(value: Decimal) -> int | float:
    """9 -> 9, 0.25 -> 0.25: a JSON number, not Pydantic's default string."""
    return int(value) if value == value.to_integral_value() else float(value)


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


# --- Taxa reference list (backend/data/taxa.json)

# Botanical naming: a genus is one capitalized word; a family name ends in "aceae".
GenusName = Annotated[str, Field(pattern=r"^[A-Z][a-z]+$")]
FamilyName = Annotated[str, Field(pattern=r"^[A-Z][a-z]+aceae$")]


def check_unique_ignoring_case(names: list[str], what: str) -> None:
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError(f"{what} must be unique")


class GenusCommonNames(StrictModel):
    en: list[NonEmptyStr] = Field(min_length=1)
    zh: list[NonEmptyStr] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique(self) -> Self:
        check_unique_ignoring_case(self.en, "English common names")
        check_unique_ignoring_case(self.zh, "Chinese common names")
        return self


class FamilyCommonNames(StrictModel):
    """Family common names in English are rarely used, so only zh is required."""

    en: list[NonEmptyStr] = []
    zh: list[NonEmptyStr] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique(self) -> Self:
        check_unique_ignoring_case(self.en, "English common names")
        check_unique_ignoring_case(self.zh, "Chinese common names")
        return self


class TaxaSource(StrictModel):
    id: Slug
    title: NonEmptyStr
    url: HttpUrl


class Family(StrictModel):
    id: Slug
    name: FamilyName
    common_names: FamilyCommonNames

    @model_validator(mode="after")
    def check_id_matches_name(self) -> Self:
        if self.id != self.name.lower():
            raise ValueError(f"id {self.id!r} must be the lowercased name")
        return self


class Genus(StrictModel):
    id: Slug
    name: GenusName
    family: Slug  # id of a Family in the same list
    # Other scientific names, e.g. a newer name the genus was moved to.
    # May equal another genus's name: Sansevieria lists "Dracaena".
    aliases: list[GenusName] = []
    common_names: GenusCommonNames
    # Why this genus is in the list (houseplant lists, trend sources).
    source_ids: list[Slug] = Field(min_length=1)

    @model_validator(mode="after")
    def check_id_matches_name(self) -> Self:
        if self.id != self.name.lower():
            raise ValueError(f"id {self.id!r} must be the lowercased name")
        return self

    @model_validator(mode="after")
    def check_aliases(self) -> Self:
        check_unique_ignoring_case(self.aliases, "aliases")
        if self.name in self.aliases:
            raise ValueError("a genus cannot be its own alias")
        return self


class TaxaList(StrictModel):
    """Genera and families users pick for groups; each genus names its family."""

    sources: list[TaxaSource]
    # Only families need min_length: every family must have a genus and every
    # genus a source, so non-empty families imply non-empty genera and sources.
    families: list[Family] = Field(min_length=1)
    genera: list[Genus]

    @model_validator(mode="after")
    def check_ids_unique(self) -> Self:
        # Groups refer to a genus or a family by id, so one id space.
        ids = [taxon.id for taxon in self.families] + [taxon.id for taxon in self.genera]
        if len(ids) != len(set(ids)):
            raise ValueError("genus and family ids must be unique together")
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source ids must be unique")
        return self

    @model_validator(mode="after")
    def check_references(self) -> Self:
        family_ids = {family.id for family in self.families}
        source_ids = {source.id for source in self.sources}
        for genus in self.genera:
            if genus.family not in family_ids:
                raise ValueError(f"{genus.name}: unknown family {genus.family!r}")
            unknown = set(genus.source_ids) - source_ids
            if unknown:
                raise ValueError(f"{genus.name}: unknown source ids {sorted(unknown)}")
        unused = family_ids - {genus.family for genus in self.genera}
        if unused:
            raise ValueError(f"families without genera: {sorted(unused)}")
        return self
