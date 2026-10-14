import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import UserSettings


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
