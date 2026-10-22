"""Pydantic types shared by every feature."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class StrictModel(BaseModel):
    """Base for all schemas: unknown fields (e.g. typos) are errors, not ignored."""

    model_config = ConfigDict(extra="forbid")


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

Days = Annotated[int, Field(gt=0)]


def decimal_to_json_number(value: Decimal) -> int | float:
    """9 -> 9, 0.25 -> 0.25: a JSON number, not Pydantic's default string."""
    return int(value) if value == value.to_integral_value() else float(value)
