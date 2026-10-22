"""What the model reads from a label photo, and the draft built from it."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, PlainSerializer

from app.core.schemas import StrictModel, decimal_to_json_number
from app.products.schemas import NpkBasis, ProductCreate, ProductType

# Looser than ProductCreate on purpose: a field the label does not show, or
# that cannot be read, stays None instead of being guessed. The server then
# validates against ProductCreate and reports what the user must fill in.
# Kept to plain types and enums, since this schema is also the model's
# structured output format.


class ExtractedNpk(StrictModel):
    n: float | None = Field(description="N as printed, in percent; null if unreadable")
    p: float | None = Field(description="P (or P2O5) as printed, in percent; null if unreadable")
    k: float | None = Field(description="K (or K2O) as printed, in percent; null if unreadable")


class ExtractedDirection(StrictModel):
    source_text: str = Field(description="This direction exactly as printed on the label")
    amount: float | None = Field(description="Dose amount; convert fractions like 1/4 to 0.25")
    amount_unit: Literal["ml", "g", "tsp", "tbsp"] | None = Field(
        description="null if the label uses another unit (e.g. a capful)"
    )
    water_volume: float | None = Field(description="Volume of water the dose goes into")
    water_unit: Literal["L", "gal"] | None = Field(description="null if another unit")
    frequency_kind: Literal["interval", "every_watering"] | None = Field(
        description="interval: every N days; every_watering: with each watering"
    )
    frequency_days: int | None = Field(
        description='Days between uses for interval, e.g. "every 2 weeks" is 14; null otherwise'
    )
    use: str | None = Field(description='What this direction is for, e.g. "maintenance"; null if not named')


# Only indoor watering directions are read for now; the rest are listed, with
# why, so the user can see what was left out.
SkipReason = Literal["outdoor", "equipment", "foliar", "other"]


class SkippedDirection(StrictModel):
    source_text: str = Field(description="The skipped instruction exactly as printed")
    reason: SkipReason = Field(
        description="outdoor: for outdoor plants; equipment: a stock solution for a siphon "
        "mixer, injector, or proportioner; foliar: a leaf spray; other: anything else"
    )


class LabelExtraction(StrictModel):
    brand: str | None
    name: str | None
    type: ProductType | None = Field(description="null if the label does not make it clear")
    npk: ExtractedNpk | None = Field(description="null if the label shows no N-P-K")
    npk_basis: NpkBasis | None = Field(
        description="oxide if P and K are given as P2O5 and K2O; elemental if as P and K; "
        "null if the label does not say"
    )
    label_directions: list[ExtractedDirection]
    notes: str | None = Field(description="Other useful facts on the label, e.g. urea-free")
    uncertain_fields: list[str] = Field(
        description='Fields read but not certain (e.g. glare), as paths like "npk.p" or '
        '"label_directions.0.amount"'
    )
    # Shown to the user, who may raise the value: the app takes the lower end
    # of a range on purpose (better to underfeed than to overfeed).
    lower_end_fields: list[str] = Field(
        description="Fields where the label gives a range and the lower end was used, as paths "
        'like "label_directions.0.amount" or "label_directions.1.frequency_days"'
    )
    skipped_directions: list[SkippedDirection] = Field(
        description="Dosing instructions on the label that were not put in label_directions"
    )


class DraftProblem(StrictModel):
    """Something the user must fix before the draft can be saved."""

    location: str  # e.g. "npk.basis", or "product" for a rule about the whole product
    message: str


class LabelDraft(StrictModel):
    """A product draft built from a label reading; nothing is saved."""

    extraction: LabelExtraction  # as the model read it, to prefill the form
    product: ProductCreate | None  # the draft, if it already passes every rule
    problems: list[DraftProblem]  # empty when product is set


class LabelCallRead(StrictModel):
    """What reading the label cost, shown with the draft."""

    model_requested: str
    model_served: str
    fell_back: bool
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: Annotated[
        Decimal | None, PlainSerializer(decimal_to_json_number, when_used="json-unless-none")
    ]


class LabelDraftResponse(LabelDraft):
    """What POST /products/draft returns: the draft plus the model call behind it."""

    call: LabelCallRead
