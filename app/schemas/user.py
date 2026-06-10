"""User schemas — response + profile update."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

LOCATION_MAX = 100


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


class UserUpdate(BaseModel):
    """PATCH /users/me body — only the fields present are updated.

    A blank/whitespace value clears the field (sets it to None).
    """

    home_city: Optional[str] = Field(None, max_length=LOCATION_MAX)
    home_country: Optional[str] = Field(None, max_length=LOCATION_MAX)

    @field_validator("home_city", "home_country", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v
