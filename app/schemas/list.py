"""Saved-list schemas — Create / Update / Response + set-membership.

Lists live at users/{uid}/lists/{listId}. The "Favorites" list has the fixed
doc id "favorites" and always exists (read-through created). Membership is the
spot id appearing in a list's spot_ids array; a spot can be in many lists.

These bodies are plain JSON (no multipart), so partial updates use Pydantic's
exclude_unset rather than the _UNSET sentinel that UserUpdate needs for forms.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

LIST_NAME_MAX = 20
LIST_DESCRIPTION_MAX = 200


class ListCreate(BaseModel):
    """POST /users/me/lists body."""

    name: str = Field(..., min_length=1, max_length=LIST_NAME_MAX)
    description: Optional[str] = Field(None, max_length=LIST_DESCRIPTION_MAX)


class ListUpdate(BaseModel):
    """PATCH /users/me/lists/{id} body — edit name and/or description (cover is
    derived). Only the fields present in the request are changed (exclude_unset);
    a blank/null description clears it."""

    name: Optional[str] = Field(None, min_length=1, max_length=LIST_NAME_MAX)
    description: Optional[str] = Field(None, max_length=LIST_DESCRIPTION_MAX)


class ListResponse(BaseModel):
    """A saved list in the overview. spot_count is derived from len(spot_ids);
    cover_photo_url is resolved at read time from the list's newest spot. The raw
    spot_ids array is intentionally not shipped here — page it via the spots route.
    """

    id: str
    name: str
    description: Optional[str] = None
    # True for the protected Favorites list (always exists, can't be renamed or
    # deleted). The client uses this to hide Edit/Delete affordances.
    is_system: bool = False
    spot_count: int
    cover_photo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SetMembershipRequest(BaseModel):
    """PATCH /users/me/spots/{spot_id}/lists body — the full desired set of lists
    this spot should belong to. The server diffs against current membership."""

    list_ids: list[str]
