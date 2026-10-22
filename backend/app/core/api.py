"""Helpers shared by the routers."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base, get_session

SessionDep = Annotated[Session, Depends(get_session)]


def get_or_404[T: Base](session: Session, model: type[T], row_id: int, label: str) -> T:
    """The row with this id, or 404 with e.g. "Product 7 not found"."""
    row = session.get(model, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} {row_id} not found")
    return row


def commit_or_conflict(session: Session, unique_index: str, detail: str) -> None:
    """Commit, turning a violation of unique_index into 409 Conflict.

    The unique index decides, instead of a lookup before the insert: two
    requests could both look, find nothing, and both insert. Any other
    IntegrityError means Pydantic let bad data through, which is a bug, so
    it is re-raised and becomes a 500. No rollback is needed here: the
    request's session is closed when the request ends, which rolls back.
    """
    try:
        session.commit()
    except IntegrityError as error:
        if unique_index in str(error.orig):
            raise HTTPException(status.HTTP_409_CONFLICT, detail) from error
        raise
