from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, HttpUrl, StringConstraints, model_validator

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Lowercase words joined by hyphens, e.g. "monstera-deliciosa".
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]

# Each care section cites the guide's sources by id.
SourceIds = Annotated[list[Slug], Field(min_length=1)]


class LocalizedText(BaseModel):
    zh: NonEmptyStr
    en: NonEmptyStr


class SeasonalInterval(BaseModel):
    spring_summer: int = Field(gt=0)
    fall_winter: int = Field(gt=0)


# PPFD (µmol/m²/s): photosynthetically active photons reaching the leaf.
# Clear midsummer noon sun peaks near this; no plant needs more.
MAX_PPFD = 2_000

Ppfd = Annotated[int, Field(ge=0, le=MAX_PPFD)]


class PpfdRange(BaseModel):
    min: Ppfd
    max: Ppfd

    @model_validator(mode="after")
    def check_max_not_below_min(self) -> Self:
        if self.max < self.min:
            raise ValueError("max must be greater than or equal to min")
        return self


WindowExposureId = Literal["strong", "gentle", "none"]


class WindowExposure(BaseModel):
    """How much direct sun a window gets; shared by all plants."""

    id: WindowExposureId
    names: LocalizedText
    how_to_tell: LocalizedText


# Shade-tolerant plants can sit up to ~20 ft (6 m) from a bright window;
# anything farther is almost certainly a data error.
MAX_WINDOW_DISTANCE_M = 6.0

WindowDistance = Annotated[float, Field(ge=0, le=MAX_WINDOW_DISTANCE_M)]


class DistanceRange(BaseModel):
    min: WindowDistance
    max: WindowDistance

    @model_validator(mode="after")
    def check_max_not_below_min(self) -> Self:
        if self.max < self.min:
            raise ValueError("max must be greater than or equal to min")
        return self


class Placement(BaseModel):
    window: WindowExposureId
    distance_m: DistanceRange
    notes: str = ""


class Light(BaseModel):
    ideal_ppfd: PpfdRange
    tolerable_ppfd: PpfdRange
    ppfd_basis: Literal["stated_by_source", "converted_from_label"]
    placement: list[Placement] = Field(min_length=1)
    notes: str = ""
    source_ids: SourceIds

    @model_validator(mode="after")
    def check_ideal_within_tolerable(self) -> Self:
        if (
            self.ideal_ppfd.min < self.tolerable_ppfd.min
            or self.ideal_ppfd.max > self.tolerable_ppfd.max
        ):
            raise ValueError("ideal_ppfd must fall within tolerable_ppfd")
        return self

    @model_validator(mode="after")
    def check_windows_unique(self) -> Self:
        windows = [p.window for p in self.placement]
        if len(windows) != len(set(windows)):
            raise ValueError("each window exposure may appear only once")
        return self


class Watering(BaseModel):
    interval_days: SeasonalInterval
    how_to_check: NonEmptyStr
    source_ids: SourceIds


class SoilComponent(BaseModel):
    component: NonEmptyStr
    parts: int = Field(gt=0)


class Soil(BaseModel):
    mix: list[SoilComponent] = Field(min_length=1)
    notes: str = ""
    source_ids: SourceIds


Month = Annotated[int, Field(ge=1, le=12)]


class Fertilizer(BaseModel):
    npk_ratio: NonEmptyStr
    dilution: NonEmptyStr
    frequency_days: int = Field(gt=0)
    pause_months: list[Month] = []
    notes: str = ""
    source_ids: SourceIds


class Source(BaseModel):
    id: Slug
    title: NonEmptyStr
    url: HttpUrl


class PlantCareGuide(BaseModel):
    id: Slug
    names: LocalizedText
    scientific_name: NonEmptyStr
    cultivar: str | None = None
    variegated: bool
    light: Light
    watering: Watering
    soil: Soil
    fertilizer: Fertilizer
    consensus: list[str] = []
    disputed: list[str] = []
    sources: list[Source]

    @model_validator(mode="after")
    def check_source_ids_unique(self) -> Self:
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source ids must be unique")
        return self

    @model_validator(mode="after")
    def check_cited_sources_exist(self) -> Self:
        known = {source.id for source in self.sources}
        for section in (self.light, self.watering, self.soil, self.fertilizer):
            unknown = set(section.source_ids) - known
            if unknown:
                raise ValueError(f"unknown source ids: {sorted(unknown)}")
        return self
