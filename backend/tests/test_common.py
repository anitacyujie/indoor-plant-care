"""Helpers shared by the routers."""

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Product
from app.routers.common import commit_or_conflict

# --- commit_or_conflict: only a violation of the given unique index becomes
# 409 (through the API, Pydantic rejects everything else first, so these call
# the function directly)

INDEX = "uq_products_brand_name"


def add_raw(session, **fields):
    session.add(Product(**({"brand": "B", "name": "N", "type": "additive"} | fields)))


def test_commit_or_conflict_turns_duplicate_into_409(session):
    add_raw(session)
    session.commit()
    add_raw(session, brand="b")
    with pytest.raises(HTTPException) as caught:
        commit_or_conflict(session, INDEX, "already exists")
    assert (caught.value.status_code, caught.value.detail) == (409, "already exists")


def test_commit_or_conflict_reraises_other_integrity_errors(session):
    add_raw(session, type="slow_release")  # breaks a CHECK, not the unique index
    with pytest.raises(IntegrityError, match="valid_type"):
        commit_or_conflict(session, INDEX, "already exists")


def test_commit_or_conflict_reraises_other_unique_index(session):
    add_raw(session)
    session.commit()
    add_raw(session, brand="b")
    with pytest.raises(IntegrityError):
        commit_or_conflict(session, "uq_some_other_index", "already exists")
