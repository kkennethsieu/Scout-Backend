"""Saved-list endpoints — per-user lists and spot membership.

All routes are scoped to the caller (users/{uid}/lists/...), so auth is the only
authorization needed — ownership is enforced by the path. The Favorites list
(fixed id "favorites") always exists and can't be renamed or deleted.
"""

from fastapi import APIRouter, Depends, Query, Response

from app.api.v1.deps import current_uid
from app.schemas.list import (
    ListCreate,
    ListResponse,
    ListsOverview,
    ListUpdate,
    SetMembershipRequest,
)
from app.schemas.pagination import PaginatedSpots
from app.services import list_service

router = APIRouter(tags=["lists"])


@router.get("/users/me/lists", response_model=ListsOverview)
async def get_lists(uid: str = Depends(current_uid)):
    """The caller's lists plus the membership map for their saved spots, Favorites
    first. Creates Favorites if missing."""
    return await list_service.list_overview(uid)


@router.post("/users/me/lists", response_model=ListResponse, status_code=201)
async def create_list(body: ListCreate, uid: str = Depends(current_uid)):
    """Create a new list, with an optional description."""
    return await list_service.create_list(uid, body.name, body.description)


@router.patch("/users/me/lists/{list_id}", response_model=ListResponse)
async def update_list(list_id: str, body: ListUpdate, uid: str = Depends(current_uid)):
    """Edit a list's name and/or description. 400 FAVORITES_PROTECTED for Favorites."""
    return await list_service.update_list(uid, list_id, body.model_dump(exclude_unset=True))


@router.delete("/users/me/lists/{list_id}", status_code=204)
async def delete_list(list_id: str, uid: str = Depends(current_uid)):
    """Delete a list. 400 FAVORITES_PROTECTED for the Favorites list."""
    await list_service.delete_list(uid, list_id)
    return Response(status_code=204)


@router.get("/users/me/lists/{list_id}/spots", response_model=PaginatedSpots)
async def get_list_spots(
    list_id: str,
    limit: int = Query(30, ge=1, le=50),
    cursor: str | None = Query(None),
    uid: str = Depends(current_uid),
):
    """Paginated spots in a list, newest first. Missing spots are skipped."""
    return await list_service.get_list_spots(uid, list_id, limit, cursor)


@router.patch("/users/me/spots/{spot_id}/lists", response_model=ListsOverview)
async def set_spot_membership(
    spot_id: str, body: SetMembershipRequest, uid: str = Depends(current_uid)
):
    """Set the exact set of lists a spot belongs to (one transaction). Returns the
    refreshed overview ({lists, memberships}) so the client re-hydrates atomically.
    Use this from the iOS "Add to list" sheet."""
    return await list_service.set_membership(uid, spot_id, body.list_ids)
