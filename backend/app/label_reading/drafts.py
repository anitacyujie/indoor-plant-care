"""Turn what the model read from a label (LabelExtraction) into a product draft.

The model only transcribes; this module decides what is missing. Fields the
model left empty are left out, so ProductCreate reports them as problems
for the user to fix, instead of anything being filled in by guesswork.
"""

from decimal import Decimal

from pydantic import ValidationError

from app.label_reading.schemas import (
    DraftProblem,
    ExtractedDirection,
    LabelDraft,
    LabelExtraction,
)
from app.products.schemas import ProductCreate


def draft_from_extraction(extraction: LabelExtraction) -> LabelDraft:
    data = extraction_to_product_data(extraction)
    try:
        product = ProductCreate.model_validate(data)
    except ValidationError as error:
        return LabelDraft(
            extraction=extraction,
            product=None,
            problems=[problem_from(detail) for detail in error.errors()],
        )
    return LabelDraft(extraction=extraction, product=product, problems=[])


def problem_from(detail) -> DraftProblem:
    # A rule on the whole product (e.g. "fertilizers must state their NPK")
    # has an empty location.
    location = ".".join(str(part) for part in detail["loc"]) or "product"
    return DraftProblem(location=location, message=detail["msg"])


def extraction_to_product_data(extraction: LabelExtraction) -> dict:
    """The ProductCreate shape, with every empty field left out."""
    data = without_none({
        "brand": extraction.brand,
        "name": extraction.name,
        "type": extraction.type,
        "notes": extraction.notes,
    })
    if extraction.npk is not None:
        npk = extraction.npk
        data["npk"] = without_none({
            "n": to_decimal(npk.n),
            "p": to_decimal(npk.p),
            "k": to_decimal(npk.k),
            "basis": extraction.npk_basis,
        })
    data["label_directions"] = [direction_data(d) for d in extraction.label_directions]
    return data


def direction_data(direction: ExtractedDirection) -> dict:
    data = without_none({
        "application": direction.application,
        "amount": direction.amount,
        "amount_unit": direction.amount_unit,
        "water_volume": direction.water_volume,
        "water_unit": direction.water_unit,
        "use": direction.use,
        "details": direction.details,
    })
    match direction.frequency_kind:
        case "interval":
            data["frequency"] = without_none({"kind": "interval", "days": direction.frequency_days})
        case "every_watering" | "as_needed":
            data["frequency"] = {"kind": direction.frequency_kind}
    return data


def to_decimal(value: float | None) -> Decimal | None:
    # str() gives the shortest form of the float ("0.2", not
    # "0.200000000000000011..."), so the printed value comes through exactly.
    # No rounding: a value with too many decimals should be reported, not fixed.
    return None if value is None else Decimal(str(value))


def without_none(fields: dict) -> dict:
    return {key: value for key, value in fields.items() if value is not None}
