"""A fake Anthropic client for tests: no network, no cost.

It records each request and returns (or raises) what the test set up.
Responses are shaped like the SDK's BetaMessage, with only the fields the
app reads.
"""

import json
from types import SimpleNamespace

import httpx2

# A complete reading of a label: one indoor direction whose dose was a range
# (the lower end used), and one outdoor direction skipped.
EXTRACTION = {
    "brand": "Dyna-Gro",
    "name": "Foliage-Pro",
    "type": "liquid_fertilizer",
    "npk": {"n": 9, "p": 3, "k": 6},
    "npk_basis": "oxide",
    "label_directions": [{
        "source_text": "1/4 to 1/2 tsp per gallon every watering",
        "amount": 0.25, "amount_unit": "tsp", "water_volume": 1, "water_unit": "gal",
        "frequency_kind": "every_watering", "frequency_days": None, "use": None,
    }],
    "notes": None,
    "uncertain_fields": [],
    "lower_end_fields": ["label_directions.0.amount"],
    "skipped_directions": [
        {"source_text": "For outdoor plants use 1/2 tsp every time you water.", "reason": "outdoor"},
    ],
}


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def response(
    content=None, stop_reason="end_turn", model="claude-opus-5-5",
    input_tokens=2000, output_tokens=800, iterations=None,
):
    """Shaped like the SDK's BetaMessage, with only the fields read_label uses."""
    return SimpleNamespace(
        content=[text_block(json.dumps(EXTRACTION))] if content is None else content,
        stop_reason=stop_reason,
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens, iterations=iterations),
    )


class FakeClient:
    """Records the request and returns (or raises) what the test set up."""

    def __init__(self, result):
        self.result = result
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, status):
    return cls("error", response=httpx2.Response(status, request=REQUEST), body=None)


