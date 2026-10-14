from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app.models import MyPlant, UserSettings, WateringEvent


def test_foreign_keys_are_enforced(session):
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


@pytest.mark.parametrize("hemisphere", ["north", "south"])
def test_user_settings_accepts_valid_row(session, hemisphere):
    session.add(UserSettings(timezone="America/Toronto", hemisphere=hemisphere))
    session.commit()
    assert session.get(UserSettings, 1).hemisphere == hemisphere


def test_user_settings_allows_only_one_row(session):
    session.add(UserSettings(timezone="America/Toronto", hemisphere="north"))
    session.commit()
    session.add(UserSettings(id=2, timezone="Australia/Sydney", hemisphere="south"))
    with pytest.raises(IntegrityError, match="single_row"):
        session.commit()


def test_user_settings_rejects_unknown_hemisphere(session):
    session.add(UserSettings(timezone="America/Toronto", hemisphere="east"))
    with pytest.raises(IntegrityError, match="valid_hemisphere"):
        session.commit()


@pytest.mark.parametrize("missing", ["timezone", "hemisphere"])
def test_user_settings_requires_field(session, missing):
    fields = {"timezone": "America/Toronto", "hemisphere": "north"}
    del fields[missing]
    session.add(UserSettings(**fields))
    with pytest.raises(IntegrityError, match=f"NOT NULL.*{missing}"):
        session.commit()


def add_plant(session, **fields):
    plant = MyPlant(**({"plant_id": "monstera-deliciosa", "nickname": "Living room"} | fields))
    session.add(plant)
    session.commit()
    return plant


def test_my_plant_gets_id_and_created_at(session):
    before = datetime.now(UTC)
    plant = add_plant(session)
    assert plant.id == 1
    assert before <= plant.created_at <= datetime.now(UTC)


def test_my_plant_allows_same_plant_and_nickname_twice(session):
    first = add_plant(session)
    second = add_plant(session)
    assert first.id != second.id


@pytest.mark.parametrize("missing", ["plant_id", "nickname"])
def test_my_plant_requires_field(session, missing):
    fields = {"plant_id": "monstera-deliciosa", "nickname": "Living room"}
    del fields[missing]
    session.add(MyPlant(**fields))
    with pytest.raises(IntegrityError, match=f"NOT NULL.*{missing}"):
        session.commit()


def test_datetime_is_read_back_in_utc(session):
    toronto_winter = timezone(timedelta(hours=-5))
    created = datetime(2026, 1, 15, 23, 30, tzinfo=toronto_winter)
    plant = add_plant(session, created_at=created)
    session.expire_all()  # force a fresh read from the database
    assert plant.created_at == created
    assert plant.created_at.tzinfo == UTC
    assert plant.created_at.day == 16  # 23:30 in Toronto is the next day in UTC


def test_datetime_without_time_zone_is_rejected(session):
    session.add(MyPlant(plant_id="monstera-deliciosa", nickname="x", created_at=datetime(2026, 1, 15)))
    with pytest.raises(StatementError, match="timezone-aware"):
        session.commit()


def count_events(session):
    return session.scalar(select(func.count()).select_from(WateringEvent))


def test_watering_event_links_both_ways(session):
    plant = add_plant(session)
    event = WateringEvent(my_plant=plant)
    session.add(event)
    session.commit()
    assert event.my_plant_id == plant.id
    assert plant.watering_events == [event]
    assert event.watered_at.tzinfo == UTC


def test_watering_event_rejects_unknown_plant(session):
    session.add(WateringEvent(my_plant_id=999))
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


def test_watering_event_requires_plant(session):
    session.add(WateringEvent())
    with pytest.raises(IntegrityError, match="NOT NULL.*my_plant_id"):
        session.commit()


def test_deleting_plant_deletes_its_watering_events(session):
    plant = add_plant(session)
    other = add_plant(session, nickname="Bedroom")
    session.add_all([WateringEvent(my_plant=plant), WateringEvent(my_plant=plant), WateringEvent(my_plant=other)])
    session.commit()

    session.delete(plant)
    session.commit()

    assert count_events(session) == 1  # only the other plant's event is left


def test_deleting_watering_event_keeps_plant_and_other_events(session):
    plant = add_plant(session)
    mistake, kept = WateringEvent(my_plant=plant), WateringEvent(my_plant=plant)
    session.add_all([mistake, kept])
    session.commit()
    assert plant.watering_events == [mistake, kept]  # loads the collection into memory

    session.delete(mistake)
    session.commit()

    # No manual refresh: commit must expire the loaded collection, so the
    # next read comes from the database without the deleted event.
    assert plant.watering_events == [kept]
    assert session.get(MyPlant, plant.id) is not None
