"""Reading a label with Claude, against a fake client: no network, no cost."""

import base64
import json
import logging
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import pytest

from app.core.config import LABEL_MODEL
from app.label_reading import reader
from app.label_reading.reader import (
    MAX_IMAGE_BYTES,
    PROMPT_VERSION,
    LabelReaderUnavailable,
    LabelReadFailed,
    LabelRefused,
    cost_usd,
    get_anthropic_client,
    read_label,
)
from app.label_reading.schemas import LabelExtraction
from fake_anthropic import EXTRACTION, REQUEST, FakeClient, response, status_error, text_block

IMAGE = b"\x89PNG fake image bytes"


def read(result, **kwargs):
    client = FakeClient(result)
    return read_label(client, IMAGE, "image/png", **kwargs), client.requests[0]


# --- a successful read


def test_returns_the_extraction():
    reading, _ = read(response())
    assert reading.extraction == LabelExtraction.model_validate(EXTRACTION)


def test_records_the_call():
    reading, _ = read(response(), model="claude-opus-5-5")
    call = reading.call
    assert (call.model_requested, call.model_served, call.fell_back) == ("claude-opus-5-5", "claude-opus-5-5", False)
    assert (call.prompt_version, call.input_tokens, call.output_tokens) == (PROMPT_VERSION, 2000, 800)
    assert call.cost_usd == Decimal("0.024")  # 2000 x $4 + 800 x $20, per million
    assert isinstance(call.latency_ms, int) and call.latency_ms >= 0


def test_text_is_found_after_other_blocks():
    blocks = [SimpleNamespace(type="thinking", thinking=""), text_block(json.dumps(EXTRACTION))]
    reading, _ = read(response(content=blocks))
    assert reading.extraction.brand == "Dyna-Gro"


def test_fallback_is_recorded_and_priced_at_the_serving_model():
    iterations = [SimpleNamespace(type="message"), SimpleNamespace(type="fallback_message")]
    reading, _ = read(response(model="claude-sonnet-5-5", iterations=iterations), model="claude-opus-5-5")
    call = reading.call
    assert (call.model_requested, call.model_served, call.fell_back) == ("claude-opus-5-5", "claude-sonnet-5-5", True)
    assert call.cost_usd == Decimal("0.012")  # Sonnet 5.5: $2 / $10


def test_unknown_model_gets_no_cost():
    reading, _ = read(response(model="claude-future-9"))
    assert reading.call.cost_usd is None


# --- the request sent to the API


def test_request_sends_the_image_and_the_instructions():
    _, request = read(response())
    image, text = request["messages"][0]["content"]
    assert image["source"]["media_type"] == "image/png"
    assert base64.standard_b64decode(image["source"]["data"]) == IMAGE
    assert text["type"] == "text"
    assert request["system"] == reader.SYSTEM_PROMPT


def test_request_asks_for_the_extraction_schema():
    _, request = read(response())
    assert request["output_config"]["format"] == {
        "type": "json_schema",
        "schema": anthropic.transform_schema(LabelExtraction),
    }


# The literal, not FALLBACK_BETA: "default" must be paired with exactly this
# header (the older -06-01 header is for the list form, and pairing them
# wrong is a 400).
def test_request_opts_into_fallback():
    _, request = read(response())
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]


def test_request_uses_the_given_model():
    _, request = read(response(), model="claude-haiku-5-5")
    assert request["model"] == "claude-haiku-5-5"


def test_request_defaults_to_the_configured_model():
    _, request = read(response())
    assert request["model"] == LABEL_MODEL


# --- answers that are not a usable extraction


def test_refusal_raises_label_refused():
    # Even with text present: stop_reason is checked before content.
    with pytest.raises(LabelRefused):
        read(response(stop_reason="refusal"))


def test_cut_off_answer_fails():
    with pytest.raises(LabelReadFailed):
        read(response(stop_reason="max_tokens"))


def test_answer_without_text_fails():
    with pytest.raises(LabelReadFailed):
        read(response(content=[SimpleNamespace(type="thinking", thinking="")]))


@pytest.mark.parametrize(
    "text",
    ["not json", json.dumps({"brand": "only a brand"}), json.dumps(EXTRACTION | {"guess": 1})],
    ids=["not-json", "missing-fields", "unknown-field"],
)
def test_answer_of_the_wrong_shape_fails(text):
    with pytest.raises(LabelReadFailed):
        read(response(content=[text_block(text)]))


# --- API errors


@pytest.mark.parametrize(
    "error",
    [
        status_error(anthropic.RateLimitError, 429),
        status_error(anthropic.InternalServerError, 500),
        status_error(anthropic.OverloadedError, 529),
        status_error(anthropic.ServiceUnavailableError, 503),
        anthropic.APIConnectionError(request=REQUEST),
        anthropic.APITimeoutError(request=REQUEST),
    ],
    ids=["rate-limit", "server-error", "overloaded", "unavailable", "connection", "timeout"],
)
def test_busy_or_unreachable_api_is_retryable(error):
    with pytest.raises(LabelReaderUnavailable) as caught:
        read(error)
    assert caught.value.retryable is True


@pytest.mark.parametrize(
    "error",
    [
        status_error(anthropic.AuthenticationError, 401),
        status_error(anthropic.APIStatusError, 402),  # billing
        status_error(anthropic.PermissionDeniedError, 403),
        status_error(anthropic.NotFoundError, 404),  # unknown model
        status_error(anthropic.BadRequestError, 400),
    ],
    ids=["bad-key", "billing", "permission", "unknown-model", "bad-request"],
)
def test_rejected_request_is_not_retryable(error):
    with pytest.raises(LabelReaderUnavailable) as caught:
        read(error)
    assert caught.value.retryable is False


# --- logging


def test_each_call_logs_usage_but_not_the_image(caplog):
    with caplog.at_level(logging.INFO, logger="app.label_reading.reader"):
        read(response())
    [record] = caplog.records
    message = record.getMessage()
    assert PROMPT_VERSION in message and "cost_usd=0.024" in message
    assert base64.standard_b64encode(IMAGE).decode() not in message


# --- cost


@pytest.mark.parametrize(
    "model, expected",
    [
        ("claude-opus-5-5", Decimal("0.024")),
        ("claude-sonnet-5-5", Decimal("0.012")),
        ("claude-haiku-5-5", Decimal("0.0006")),
    ],
)
def test_cost_uses_each_models_price(model, expected):
    assert cost_usd(model, 2000, 800) == expected


def test_cost_weighs_input_and_output_separately():
    # Swapping the counts changes the cost: output tokens cost 5x input on Opus 5.5.
    assert cost_usd("claude-opus-5-5", 1_000_000, 0) == Decimal("4")
    assert cost_usd("claude-opus-5-5", 0, 1_000_000) == Decimal("20")


# --- the client dependency


def test_client_is_created_once(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    get_anthropic_client.cache_clear()
    try:
        assert get_anthropic_client() is get_anthropic_client()
    finally:
        get_anthropic_client.cache_clear()


# --- the upload size limit


# The API takes 10 MB per image after base64 encoding (4 bytes out for every 3
# in), so the raw limit must leave room for that. 10 MB is read as 10,000,000
# bytes, the stricter reading.
def test_size_limit_fits_the_api_after_base64():
    assert len(base64.standard_b64encode(b"x" * MAX_IMAGE_BYTES)) <= 10_000_000
