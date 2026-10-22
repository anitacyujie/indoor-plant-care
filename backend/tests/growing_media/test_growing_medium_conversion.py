"""Conversion between the API shape (GrowingMediumCreate / Read) and the tables."""

from datetime import datetime

from sqlalchemy import func, select

from app.growing_media.models import GrowingMedium, GrowingMediumComponent
from app.growing_media.router import fill_medium, medium_to_read
from app.growing_media.schemas import GrowingMediumCreate


def save_and_reload(session, data: dict) -> GrowingMedium:
    medium = fill_medium(GrowingMedium(), GrowingMediumCreate.model_validate(data))
    session.add(medium)
    session.commit()
    session.expire_all()  # force a fresh read from the database
    return medium


def refill(session, medium: GrowingMedium, data: dict) -> None:
    fill_medium(medium, GrowingMediumCreate.model_validate(data))
    session.commit()
    session.expire_all()


def without_saved_fields(read) -> dict:
    return read.model_dump(exclude={"id", "created_at"})


def count_components(session):
    return session.scalar(select(func.count()).select_from(GrowingMediumComponent))


# --- round trip


def test_full_medium_round_trips(session, medium):
    read = medium_to_read(save_and_reload(session, medium))
    assert without_saved_fields(read) == GrowingMediumCreate.model_validate(medium).model_dump()


def test_hydro_without_components_round_trips(session, medium):
    medium |= {"method": "hydro", "components": []}
    read = medium_to_read(save_and_reload(session, medium))
    assert (read.method, read.components) == ("hydro", [])


def test_read_includes_id_and_created_at(session, medium):
    read = medium_to_read(save_and_reload(session, medium))
    assert read.id == 1
    assert isinstance(read.created_at, datetime)


# --- how components map to rows


def test_components_map_to_rows(session, medium):
    saved = save_and_reload(session, medium)
    rows = [(r.component, r.other_name, r.parts) for r in saved.components]
    assert rows == [("bark", None, 2), ("perlite", None, 1), ("other", "zeolite", 1)]


# Order is not part of a medium: any input order reads back the same way.
def test_input_order_does_not_matter(session, medium):
    medium["components"].reverse()
    read = medium_to_read(save_and_reload(session, medium))
    assert [c.model_dump() for c in read.components] == list(reversed(medium["components"]))


# --- update: filling an existing medium replaces it


def test_fill_existing_medium_replaces_fields_and_components(session, medium):
    saved = save_and_reload(session, medium)
    refill(session, saved, medium | {
        "name": "LECA",
        "method": "semi_hydro",
        "components": [{"component": "leca", "parts": 1}],
    })
    assert (saved.name, saved.method) == ("LECA", "semi_hydro")
    assert [r.component for r in saved.components] == ["leca"]
    assert count_components(session) == 1  # old rows deleted, not left behind


# Regression guard: kept components must not collide with the rows they
# replace (same listed id, same other name).
def test_fill_existing_medium_with_same_components(session, medium):
    saved = save_and_reload(session, medium)
    refill(session, saved, medium)
    assert len(saved.components) == 3


def test_fill_existing_medium_keeps_other_media_components(session, medium):
    saved = save_and_reload(session, medium)
    other = save_and_reload(session, medium | {"name": "Hoya mix"})
    refill(session, saved, medium | {"components": [{"component": "leca", "parts": 1}]})
    assert len(other.components) == 3
