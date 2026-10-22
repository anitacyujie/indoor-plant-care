"""The taxa reference list (backend/data/taxa.json)."""

from typing import Annotated, Self

from pydantic import Field, HttpUrl, model_validator

from app.core.schemas import NonEmptyStr, StrictModel

# Lowercase words joined by hyphens, e.g. "monstera-deliciosa".
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]

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
