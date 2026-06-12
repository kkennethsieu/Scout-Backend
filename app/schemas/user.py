"""User schemas — response + profile update."""

from datetime import datetime
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, Field, field_validator

LOCATION_MAX = 100
DISPLAY_NAME_MAX = 100

# Sentinel default for the editable string fields. Under multipart/form-data we
# can't use Pydantic's exclude_unset (Form binding sets every field), so a field
# left at this sentinel means "the client didn't send it → leave unchanged",
# which a real value (including blank) is distinguishable from.
_UNSET = "\x00__UNSET__\x00"


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    photo_url: str | None
    created_at: datetime
    # Maintained atomically as the user creates/deletes reviews.
    review_count: int = 0
    # Where the user is from — set via PATCH /users/me, None until provided.
    home_city: Optional[str] = None
    home_country: Optional[str] = None
    # Notification preferences — default on, toggled via PATCH /users/me.
    email_notifications: bool = True
    push_notifications: bool = True


class UserUpdate(BaseModel):
    """PATCH /users/me body — multipart/form-data, partial update.

    Only the fields the client actually sends are changed (see _UNSET). For
    `home_city` / `home_country` a blank/whitespace value clears the field to
    None. `display_name` cannot be cleared (it's non-nullable on the response),
    so a blank value is ignored. `email` is intentionally absent — it's the
    Firebase Auth login identity and stays read-only. The profile photo rides
    along as an optional UploadFile (same pattern as review submission), handled
    in the router; it isn't part of to_update_dict().
    """

    display_name: str = Field(_UNSET, max_length=DISPLAY_NAME_MAX)
    home_city: str = Field(_UNSET, max_length=LOCATION_MAX)
    home_country: str = Field(_UNSET, max_length=LOCATION_MAX)
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    photo: Optional[UploadFile] = None

    @field_validator("display_name", "home_city", "home_country", mode="before")
    @classmethod
    def _strip_or_keep_sentinel(cls, v):
        """Leave the unset sentinel untouched; strip real string values."""
        if isinstance(v, str) and v != _UNSET:
            return v.strip()
        return v

    def to_update_dict(self) -> dict:
        """Build the Firestore merge dict, applying partial-update semantics.

        Skips fields the client didn't send (still the sentinel), maps blank
        city/country to None (clears the field), drops a blank display_name, and
        includes the notification booleans only when explicitly provided. Excludes
        `photo`, which the router uploads and merges as `photo_url` separately.
        """
        updates: dict = {}

        if self.display_name != _UNSET and self.display_name:
            updates["display_name"] = self.display_name

        for field in ("home_city", "home_country"):
            value = getattr(self, field)
            if value != _UNSET:
                updates[field] = value or None

        if self.email_notifications is not None:
            updates["email_notifications"] = self.email_notifications
        if self.push_notifications is not None:
            updates["push_notifications"] = self.push_notifications

        return updates
