"""Read a fertilizer label photo with Claude and return what it transcribed.

This module only talks to the model. Turning the result into a product draft
is app/label_drafts.py; the upload endpoint is in the products router.
Every call records model, prompt version, tokens, latency, and cost.
"""

import base64
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache

import anthropic
from pydantic import ValidationError

from app.config import LABEL_MODEL
from app.schemas import LabelExtraction

logger = logging.getLogger(__name__)

# Bump on every change to SYSTEM_PROMPT or USER_TEXT, so eval runs can be
# compared by prompt version.
PROMPT_VERSION = "label-v1"

SYSTEM_PROMPT = """\
You read photos of fertilizer and plant-care product labels and transcribe \
what is printed, for a grower who checks every field before saving.

Transcribe; do not infer. If something is not printed on the label, or you \
cannot read it, use null. The grower fills in gaps, so a wrong guess is worse \
than null.

- npk: the guaranteed analysis numbers exactly as printed.
- npk_basis: "oxide" when phosphorus and potassium are given as P2O5 \
(phosphate) and K2O (potash); "elemental" when given as P and K. If the label \
does not show which, null.
- type: liquid_fertilizer for a liquid concentrate, soluble_powder for a \
powder or crystals dissolved in water, additive for a product with no N-P-K \
analysis. Null if unclear.
- label_directions: one entry per distinct dosing instruction for watering \
plants (skip foliar sprays and hydroponic reservoirs unless they are the only \
instructions). Copy the instruction into source_text as printed. Write \
fractions as decimals (1/4 is 0.25). Use only the listed units; for any other \
unit (such as a capful) use null. For frequency, use every_watering when it \
goes in with each watering, otherwise interval with the number of days \
(weekly 7, every two weeks 14, monthly 30). Name each direction in use when \
the label names it (for example "maintenance" or "seedlings").
- notes: other facts a grower would want, such as "urea-free"; not marketing \
claims.
- uncertain_fields: paths of fields you filled in but could not read clearly, \
such as "npk.p" or "label_directions.0.amount".
"""

USER_TEXT = "Transcribe this product label."

MAX_TOKENS = 16000

# Fallback on a safety decline: the API re-runs a declined request on the model
# Anthropic recommends for that decline, inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# US$ per million tokens (input, output), from the Anthropic price list as of
# 2026-10-06. Prices change: a model missing here gets no cost, not a guess.
PRICES_PER_MTOK = {
    "claude-opus-5-5": (Decimal("4.00"), Decimal("20.00")),
    "claude-sonnet-5-5": (Decimal("2.00"), Decimal("10.00")),
    "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50")),  # prompts up to 100K tokens
}


class LabelReadError(Exception):
    """Base class: reading the label did not produce an extraction."""


class LabelRefused(LabelReadError):
    """The model declined to read the image (a safety decline, even after fallback)."""


class LabelReadFailed(LabelReadError):
    """The model answered, but not with a usable extraction (cut off, not valid JSON, wrong shape)."""


class LabelReaderUnavailable(LabelReadError):
    """The API could not be used: overloaded, unreachable, or misconfigured (key, billing)."""

    def __init__(self, message: str, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class LabelCall:
    """What one model call used, for logs and evals."""

    model_requested: str
    model_served: str  # differs when a fallback ran
    fell_back: bool
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: Decimal | None  # None when the model has no price in PRICES_PER_MTOK


@dataclass(frozen=True)
class LabelReading:
    extraction: LabelExtraction
    call: LabelCall


@lru_cache
def get_anthropic_client() -> anthropic.Anthropic:
    """A FastAPI dependency; tests override it with a fake client.

    The SDK reads ANTHROPIC_API_KEY from the environment itself.
    """
    return anthropic.Anthropic()


def read_label(
    client: anthropic.Anthropic, image: bytes, media_type: str, model: str = LABEL_MODEL
) -> LabelReading:
    started = time.perf_counter()
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={
                "format": {"type": "json_schema", "schema": anthropic.transform_schema(LabelExtraction)}
            },
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.standard_b64encode(image).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": USER_TEXT},
                ],
            }],
        )
    # The SDK has already retried connection errors, 429, and 5xx twice by the
    # time these reach us.
    except anthropic.APIConnectionError as error:  # includes APITimeoutError
        logger.warning("label reader unreachable: %s", type(error).__name__)
        raise LabelReaderUnavailable("the model API is unreachable", retryable=True) from error
    except anthropic.APIStatusError as error:
        # Decided by status code, not class: 529 (overloaded) and 503 have
        # their own classes outside InternalServerError.
        if error.status_code == 429 or error.status_code >= 500:
            logger.warning("label reader busy: %s %s", error.status_code, type(error).__name__)
            raise LabelReaderUnavailable("the model API is busy", retryable=True) from error
        # Key, billing, permission, unknown model, or a request we built wrong:
        # retrying will not help, and the details belong in the server log.
        logger.error("label reader request failed: %s %s", error.status_code, type(error).__name__)
        raise LabelReaderUnavailable("the model API rejected the request", retryable=False) from error

    call = call_record(response, model, started)
    logger.info(
        "label read: model=%s served_by=%s fell_back=%s prompt=%s in=%d out=%d ms=%d cost_usd=%s",
        call.model_requested, call.model_served, call.fell_back, call.prompt_version,
        call.input_tokens, call.output_tokens, call.latency_ms, call.cost_usd,
    )
    return LabelReading(extraction=extraction_from(response), call=call)


def extraction_from(response) -> LabelExtraction:
    # Check stop_reason before reading content.
    if response.stop_reason == "refusal":
        raise LabelRefused("the model declined to read this image")
    if response.stop_reason == "max_tokens":
        raise LabelReadFailed("the answer was cut off at the token limit")
    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise LabelReadFailed("the answer had no text")
    try:
        return LabelExtraction.model_validate_json(text)
    except ValidationError as error:  # not JSON, or JSON of the wrong shape
        raise LabelReadFailed("the answer did not match the extraction schema") from error


def call_record(response, model_requested: str, started: float) -> LabelCall:
    usage = response.usage
    fell_back = any(entry.type == "fallback_message" for entry in usage.iterations or [])
    return LabelCall(
        model_requested=model_requested,
        model_served=response.model,
        fell_back=fell_back,
        prompt_version=PROMPT_VERSION,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        latency_ms=round((time.perf_counter() - started) * 1000),
        cost_usd=cost_usd(response.model, usage.input_tokens, usage.output_tokens),
    )


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Cost at list price. Approximate after a fallback, which bills each attempt separately."""
    prices = PRICES_PER_MTOK.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
