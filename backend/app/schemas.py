from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class StrictModel(BaseModel):
    """Base for all schemas: unknown fields (e.g. typos) are errors, not ignored."""

    model_config = ConfigDict(extra="forbid")


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Lowercase words joined by hyphens, e.g. "monstera-deliciosa".
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]

Days = Annotated[int, Field(gt=0)]


class SoilComponent(StrictModel):
    component: NonEmptyStr
    parts: int = Field(gt=0)
