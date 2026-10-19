"""Database constraints on growing_media and growing_medium_components."""

from typing import get_args

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import GrowingMedium, GrowingMediumComponent
from app.schemas import MediumComponentId


def make_medium(**fields):
    return GrowingMedium(**({"name": "Aroid mix", "method": "soil"} | fields))


def make_component(**fields):
    return GrowingMediumComponent(**({"position": 0, "component": "bark", "parts": 2} | fields))


def save(session, row):
    session.add(row)
    session.commit()
    return row


def rejected(session, row, constraint):
    session.add(row)
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


@pytest.fixture
def medium(session):
    return save(session, make_medium())


def add_component(session, medium, **fields):
    component = make_component(**fields)
    medium.components.append(component)
    session.commit()
    return component


def rejected_component(session, medium, constraint, **fields):
    medium.components.append(make_component(**fields))
    with pytest.raises(IntegrityError, match=constraint):
        session.commit()


def count_components(session):
    return session.scalar(select(func.count()).select_from(GrowingMediumComponent))


# --- growing_media


def test_medium_round_trips(session, medium):
    session.expire_all()
    assert (medium.id, medium.name, medium.method, medium.notes) == (1, "Aroid mix", "soil", "")
    assert medium.created_at is not None


@pytest.mark.parametrize("missing", ["name", "method"])
def test_medium_required_column(session, missing):
    rejected(session, make_medium(**{missing: None}), f"NOT NULL.*{missing}")


@pytest.mark.parametrize("blank", ["", "   "])
def test_medium_blank_name_rejected(session, blank):
    rejected(session, make_medium(name=blank), "medium_name_not_blank")


@pytest.mark.parametrize("method", ["soil", "semi_hydro", "hydro"])
def test_each_method_accepted(session, method):
    save(session, make_medium(method=method))


def test_unknown_method_rejected(session):
    rejected(session, make_medium(method="water"), "valid_method")


@pytest.mark.parametrize("name", ["Aroid mix", "AROID MIX"], ids=["same", "different-case"])
def test_duplicate_medium_name_rejected(session, medium, name):
    rejected(session, make_medium(name=name), "UNIQUE")


# A medium with no components is allowed here; "soil and semi-hydro need a
# component" spans rows, so only Pydantic enforces it.
def test_medium_without_components_allowed_in_database(session, medium):
    assert medium.components == []


# --- components: link to the medium and order


def test_components_are_read_in_position_order(session, medium):
    add_component(session, medium, position=1, component="perlite")
    add_component(session, medium, position=0, component="bark")
    session.expire_all()
    assert [c.component for c in medium.components] == ["bark", "perlite"]


def test_unknown_medium_rejected(session):
    rejected(session, make_component(growing_medium_id=999), "FOREIGN KEY")


def test_deleting_medium_deletes_its_components(session, medium):
    other = save(session, make_medium(name="Orchid bark"))
    add_component(session, medium, position=0, component="bark")
    add_component(session, medium, position=1, component="perlite")
    add_component(session, other)

    session.delete(medium)
    session.commit()

    assert count_components(session) == 1  # only the other medium's component is left


def test_deleting_component_keeps_medium(session, medium):
    component = add_component(session, medium)
    session.delete(component)
    session.commit()
    session.expire_all()
    assert session.get(GrowingMedium, medium.id) is not None


@pytest.mark.parametrize("column", ["growing_medium_id", "position", "component", "parts"])
def test_component_required_column(session, medium, column):
    rejected(session, make_component(**({"growing_medium_id": medium.id} | {column: None})), f"NOT NULL.*{column}")


def test_negative_position_rejected(session, medium):
    rejected_component(session, medium, "medium_component_position_not_negative", position=-1)


def test_duplicate_position_rejected(session, medium):
    add_component(session, medium, position=0, component="bark")
    rejected_component(session, medium, "UNIQUE", position=0, component="perlite")


@pytest.mark.parametrize("bad", [0, -1])
def test_parts_must_be_positive(session, medium, bad):
    rejected_component(session, medium, "parts_positive", parts=bad)


# --- which component, and its name


@pytest.mark.parametrize("component_id", [*get_args(MediumComponentId)])
def test_each_listed_component_accepted(session, medium, component_id):
    add_component(session, medium, component=component_id)


def test_unknown_component_rejected(session, medium):
    rejected_component(session, medium, "valid_component", component="sand")


def test_other_with_name_accepted(session, medium):
    add_component(session, medium, component="other", other_name="zeolite")


@pytest.mark.parametrize("name", [None, "", "   "], ids=["missing", "empty", "blank"])
def test_other_needs_a_name(session, medium, name):
    rejected_component(session, medium, "other_name_only_for_other", component="other", other_name=name)


def test_listed_component_cannot_have_a_name(session, medium):
    rejected_component(session, medium, "other_name_only_for_other", component="bark", other_name="bark")


# --- each material once per medium


def test_duplicate_listed_component_rejected(session, medium):
    add_component(session, medium, position=0, component="bark")
    rejected_component(session, medium, "UNIQUE", position=1, component="bark")


@pytest.mark.parametrize("second", ["zeolite", "ZEOLITE"], ids=["same", "different-case"])
def test_duplicate_other_name_rejected(session, medium, second):
    add_component(session, medium, position=0, component="other", other_name="zeolite")
    rejected_component(session, medium, "UNIQUE", position=1, component="other", other_name=second)


def test_several_other_components_accepted(session, medium):
    add_component(session, medium, position=0, component="other", other_name="zeolite")
    add_component(session, medium, position=1, component="other", other_name="rice hulls")
    assert count_components(session) == 2


def test_same_component_in_two_media_accepted(session, medium):
    other = save(session, make_medium(name="Orchid bark"))
    add_component(session, medium, component="bark")
    add_component(session, other, component="bark")


def test_same_other_name_in_two_media_accepted(session, medium):
    other = save(session, make_medium(name="Orchid bark"))
    add_component(session, medium, component="other", other_name="zeolite")
    add_component(session, other, component="other", other_name="zeolite")


# Same method and components under another name is allowed on purpose: two
# media may match today and be adjusted apart later. The app should warn
# instead (see "Duplicate growing medium warning" in docs/ideas.md).
def test_identical_media_with_different_names_allowed(session, medium):
    twin = save(session, make_medium(name="Hoya mix"))
    for row in (medium, twin):
        add_component(session, row, position=0, component="bark", parts=2)
        add_component(session, row, position=1, component="perlite", parts=1)
    assert session.scalar(select(func.count()).select_from(GrowingMedium)) == 2
