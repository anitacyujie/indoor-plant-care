from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, HttpUrl, StringConstraints, model_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Names(BaseModel):
    zh: NonEmptyStr
    en: NonEmptyStr


class SeasonalInterval(BaseModel):
    spring_summer: int = Field(gt=0)
    fall_winter: int = Field(gt=0)


# Peak direct sunlight at ground level; no plant needs more than this.
MAX_LUX = 100_000

Lux = Annotated[int, Field(ge=0, le=MAX_LUX)]


class LuxRange(BaseModel):
    min: Lux
    max: Lux

    @model_validator(mode="after")
    def check_max_not_below_min(self) -> Self:
        if self.max < self.min:
            raise ValueError("max must be greater than or equal to min")
        return self


class Light(BaseModel):
    ideal_lux: LuxRange
    tolerable_lux: LuxRange
    lux_basis: Literal["stated_by_source", "converted_from_label"]
    notes: str = ""
    
class Watering(BaseModel):
    interval_days: SeasonalInterval
    how_to_check: NonEmptyStr


class SoilComponent(BaseModel):
    component: NonEmptyStr
    parts: int = Field(gt=0)


class Soil(BaseModel):
    mix: list[SoilComponent] = Field(min_length=1)
    notes: str = ""


Month = Annotated[int, Field(ge=1, le=12)]


class Fertilizer(BaseModel):
    npk_ratio: NonEmptyStr
    dilution: NonEmptyStr
    frequency_days: int = Field(gt=0)
    pause_months: list[Month] = []
    notes: str = ""


class Source(BaseModel):
    title: NonEmptyStr
    url: HttpUrl


class PlantCareGuide(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    names: Names
    scientific_name: NonEmptyStr
    cultivar: str | None = None
    variegated: bool
    light: Light
    watering: Watering
    soil: Soil
    fertilizer: Fertilizer
    consensus: list[str] = []
    disputed: list[str] = []
    sources: list[Source] = Field(min_length=1)