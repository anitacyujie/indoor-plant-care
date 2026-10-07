from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl
from typing import Literal


class LuxRange(BaseModel):
    min: int = Field(ge=0)
    max: int | None = None


class Light(BaseModel):
    ideal_lux: LuxRange
    minimum_lux: int = Field(ge=0)
    lux_basis: Literal["stated_by_source", "converted_from_label"]
    notes: str = ""


class Names(BaseModel):
    zh: str
    en: str


class SeasonalInterval(BaseModel):
    spring_summer: int = Field(gt=0)
    fall_winter: int = Field(gt=0)


class Watering(BaseModel):
    interval_days: SeasonalInterval
    how_to_check: str


class SoilComponent(BaseModel):
    component: str
    parts: int = Field(gt=0)


class Soil(BaseModel):
    mix: list[SoilComponent] = Field(min_length=1)
    notes: str = ""


Month = Annotated[int, Field(ge=1, le=12)]


class Fertilizer(BaseModel):
    npk_ratio: str
    dilution: str
    frequency_days: int = Field(gt=0)
    pause_months: list[Month] = []
    notes: str = ""


class Source(BaseModel):
    title: str
    url: HttpUrl


class PlantCareGuide(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    names: Names
    scientific_name: str
    cultivar: str | None = None
    variegated: bool
    light: Light
    watering: Watering
    soil: Soil
    fertilizer: Fertilizer
    consensus: list[str] = []
    disputed: list[str] = []
    sources: list[Source] = Field(min_length=1)