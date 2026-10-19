"""Growing medium endpoints, and conversion between the API shape and the tables.

A component is a ListedMediumComponent or an OtherMediumComponent in the API,
and one row with a component id (or "other" plus a name) in the table.
Components have no order of their own; they are read back with the most
parts first, then by name.
"""

from fastapi import APIRouter, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import object_session, selectinload

from app.models import GrowingMedium, GrowingMediumComponent
from app.routers.common import SessionDep, commit_or_conflict, get_or_404
from app.schemas import (
    GrowingMediumCreate,
    GrowingMediumRead,
    ListedMediumComponent,
    MediumComponent,
    OtherMediumComponent,
)


def fill_medium(medium: GrowingMedium, data: GrowingMediumCreate) -> GrowingMedium:
    """Write data into medium, replacing all of its components.

    Used for both create (a new GrowingMedium) and update (an existing one).
    On update the old components are deleted in the open transaction, so the
    caller must commit or roll back afterwards.
    """
    session = object_session(medium)
    if session is None:  # a new medium: nothing saved, nothing to delete
        return write_medium(medium, data)

    # Same reasons as fill_product: one DELETE that runs right away, because
    # a flush inserts before it deletes and kept components would collide
    # with the rows they replace; no_autoflush, so a duplicate name fails at
    # commit (409) rather than here.
    with session.no_autoflush:
        session.execute(
            delete(GrowingMediumComponent).where(
                GrowingMediumComponent.growing_medium_id == medium.id
            )
        )
        return write_medium(medium, data)


def write_medium(medium: GrowingMedium, data: GrowingMediumCreate) -> GrowingMedium:
    medium.name = data.name
    medium.method = data.method
    medium.notes = data.notes
    medium.components = [component_to_row(component) for component in data.components]
    return medium


def component_to_row(component: MediumComponent) -> GrowingMediumComponent:
    match component:
        case OtherMediumComponent(name=name):
            component_id, other_name = "other", name
        case ListedMediumComponent(component=component_id):
            other_name = None
    return GrowingMediumComponent(
        component=component_id,
        other_name=other_name,
        parts=component.parts,
    )


def medium_to_read(medium: GrowingMedium) -> GrowingMediumRead:
    return GrowingMediumRead(
        id=medium.id,
        created_at=medium.created_at,
        name=medium.name,
        method=medium.method,
        components=[row_to_component(row) for row in medium.components],
        notes=medium.notes,
    )


def row_to_component(row: GrowingMediumComponent) -> MediumComponent:
    if row.component == "other":
        return OtherMediumComponent(component="other", name=row.other_name, parts=row.parts)
    return ListedMediumComponent(component=row.component, parts=row.parts)


router = APIRouter(prefix="/growing-media", tags=["growing media"])

DUPLICATE = ("uq_growing_media_name", "A growing medium with this name already exists")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_medium(data: GrowingMediumCreate, session: SessionDep) -> GrowingMediumRead:
    medium = fill_medium(GrowingMedium(), data)
    session.add(medium)
    commit_or_conflict(session, *DUPLICATE)
    return medium_to_read(medium)


@router.get("")
def list_media(session: SessionDep) -> list[GrowingMediumRead]:
    media = session.scalars(
        select(GrowingMedium)
        # Load all components in one extra query, not one query per medium.
        .options(selectinload(GrowingMedium.components))
        .order_by(func.lower(GrowingMedium.name))
    )
    return [medium_to_read(medium) for medium in media]


@router.get("/{medium_id}")
def get_medium(medium_id: int, session: SessionDep) -> GrowingMediumRead:
    return medium_to_read(get_or_404(session, GrowingMedium, medium_id, "Growing medium"))
