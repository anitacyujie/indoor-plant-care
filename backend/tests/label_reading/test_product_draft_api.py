"""POST /products/draft with a fake Claude client: no network, no cost."""

import base64
import json

import anthropic
import pytest

from app.label_reading.reader import MAX_IMAGE_BYTES, PROMPT_VERSION, get_anthropic_client
from app.main import app
from fake_anthropic import EXTRACTION, REQUEST, FakeClient, response, status_error, text_block

PNG = b"\x89PNG\r\n\x1a\n" + b"rest of a png"
JPEG = b"\xff\xd8\xff\xe0" + b"rest of a jpeg"
GIF = b"GIF89a" + b"rest of a gif"
GIF87 = b"GIF87a" + b"rest of an older gif"
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"rest of a webp"


@pytest.fixture
def model(client):
    """Installs a fake Claude client; set .result to what the model returns."""
    fake = FakeClient(response())
    app.dependency_overrides[get_anthropic_client] = lambda: fake
    return fake  # the client fixture clears the override afterwards


def upload(client, data=PNG, filename="label.png", content_type="image/png"):
    return client.post("/products/draft", files={"photo": (filename, data, content_type)})


def answer(extraction):
    return response(content=[text_block(json.dumps(extraction))])


# --- a reading becomes a draft


def test_complete_label_gives_a_draft_ready_to_save(client, model):
    result = upload(client)
    assert result.status_code == 200
    body = result.json()
    assert body["problems"] == []
    assert body["product"]["brand"] == "Dyna-Gro"
    assert body["product"]["npk"] == {"n": 9, "p": 3, "k": 6, "basis": "oxide"}
    assert body["extraction"] == EXTRACTION


def test_incomplete_label_gives_a_draft_with_problems(client, model):
    model.result = answer(EXTRACTION | {"npk_basis": None})
    body = upload(client).json()
    assert body["product"] is None
    assert [p["location"] for p in body["problems"]] == ["npk.basis"]



# What the UI needs to explain the draft: ranges taken at the lower end and
# directions that were left out.
def test_draft_tells_which_values_were_ranges_and_what_was_skipped(client, model):
    extraction = upload(client).json()["extraction"]
    assert extraction["lower_end_fields"] == ["label_directions.0.amount"]
    assert extraction["skipped_directions"] == [
        {"source_text": "For outdoor plants use 1/2 tsp every time you water.", "reason": "outdoor"},
    ]

def test_response_includes_the_call(client, model):
    call = upload(client).json()["call"]
    assert call["model_served"] == "claude-opus-5-5"
    assert call["prompt_version"] == PROMPT_VERSION
    assert (call["input_tokens"], call["output_tokens"]) == (2000, 800)
    assert call["cost_usd"] == 0.024  # a JSON number, not a string


def test_draft_does_not_save_the_product(client, model):
    upload(client)
    assert client.get("/products").json() == []


def test_photo_reaches_the_model_unchanged(client, model):
    upload(client)
    image = model.requests[0]["messages"][0]["content"][0]
    assert base64.standard_b64decode(image["source"]["data"]) == PNG


# --- which files are accepted


@pytest.mark.parametrize(
    "data, media_type",
    [(PNG, "image/png"), (JPEG, "image/jpeg"), (GIF, "image/gif"), (GIF87, "image/gif"), (WEBP, "image/webp")],
    ids=["png", "jpeg", "gif", "gif87a", "webp"],
)
def test_each_supported_format_is_sent_with_its_media_type(client, model, data, media_type):
    assert upload(client, data=data).status_code == 200
    image = model.requests[0]["messages"][0]["content"][0]
    assert image["source"]["media_type"] == media_type


# The format comes from the bytes, not from the name or the browser's type.
def test_format_is_taken_from_the_content_not_the_declared_type(client, model):
    assert upload(client, data=JPEG, filename="label.png", content_type="image/png").status_code == 200
    assert model.requests[0]["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"


@pytest.mark.parametrize(
    "data",
    [b"plain text pretending to be a png", b"%PDF-1.7 a pdf", b"RIFF\x00\x00\x00\x00WAVEfmt ", b""],
    ids=["text", "pdf", "wav", "empty"],
)
def test_unsupported_file_returns_415_without_calling_the_model(client, model, data):
    result = upload(client, data=data)
    assert result.status_code == 415
    assert "JPEG, PNG, GIF, or WebP" in result.json()["detail"]
    assert model.requests == []


def test_photo_at_the_size_limit_is_accepted(client, model):
    data = PNG + b"\x00" * (MAX_IMAGE_BYTES - len(PNG))
    assert upload(client, data=data).status_code == 200


def test_oversized_photo_returns_413_without_calling_the_model(client, model):
    data = PNG + b"\x00" * (MAX_IMAGE_BYTES + 1 - len(PNG))
    assert upload(client, data=data).status_code == 413
    assert model.requests == []


def test_missing_photo_returns_422(client, model):
    assert client.post("/products/draft").status_code == 422


# --- when reading fails


def test_refusal_returns_422(client, model):
    model.result = response(stop_reason="refusal")
    result = upload(client)
    assert result.status_code == 422
    assert "could not be read" in result.json()["detail"]


def test_unusable_answer_returns_502(client, model):
    model.result = response(content=[text_block("not json")])
    assert upload(client).status_code == 502


@pytest.mark.parametrize(
    "error",
    [status_error(anthropic.OverloadedError, 529), anthropic.APIConnectionError(request=REQUEST),
     status_error(anthropic.AuthenticationError, 401)],
    ids=["overloaded", "connection", "bad-key"],
)
def test_unavailable_model_returns_503(client, model, error):
    model.result = error
    result = upload(client)
    assert result.status_code == 503
    assert "unavailable" in result.json()["detail"]
