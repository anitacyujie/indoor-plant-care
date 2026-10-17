from typing import get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SoilComponent, SoilComponentId

# SoilComponent is a union, not a model class, so it is validated through a
# TypeAdapter instead of SoilComponent.model_validate.
soil_component = TypeAdapter(SoilComponent)


def rejects(data):
    with pytest.raises(ValidationError):
        soil_component.validate_python(data)


@pytest.mark.parametrize("component_id", get_args(SoilComponentId))
def test_each_listed_component_accepted(component_id):
    result = soil_component.validate_python({"component": component_id, "parts": 2})
    assert result.component == component_id


def test_other_with_name_accepted():
    result = soil_component.validate_python(
        {"component": "other", "name": "zeolite", "parts": 1}
    )
    assert result.name == "zeolite"


def test_other_requires_name():
    rejects({"component": "other", "parts": 1})


@pytest.mark.parametrize("blank", ["", "   "])
def test_other_rejects_blank_name(blank):
    rejects({"component": "other", "name": blank, "parts": 1})


def test_listed_component_rejects_name():
    rejects({"component": "perlite", "name": "perlite", "parts": 1})


@pytest.mark.parametrize("bad_id", ["sand", "Perlite", ""])
def test_unknown_component_rejected(bad_id):
    rejects({"component": bad_id, "parts": 1})


def test_parts_accepts_one():
    assert soil_component.validate_python({"component": "bark", "parts": 1}).parts == 1


@pytest.mark.parametrize("bad_parts", [0, -1, 1.5])
def test_parts_must_be_positive_whole_number(bad_parts):
    rejects({"component": "bark", "parts": bad_parts})


@pytest.mark.parametrize(
    "data",
    [{"component": "bark"}, {"component": "other", "name": "zeolite"}],
    ids=["listed", "other"],
)
def test_parts_is_required(data):
    rejects(data)
