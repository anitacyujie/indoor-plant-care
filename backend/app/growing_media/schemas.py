"""Growing media as the API accepts and returns them."""

from datetime import datetime
from typing import Annotated, Literal, Self, get_args

from pydantic import Field, model_validator

from app.core.schemas import NonEmptyStr, StrictModel


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


class GrowingMediumRead(GrowingMediumCreate):
    """A saved growing medium, as the API returns it."""

    id: int
    created_at: datetime
