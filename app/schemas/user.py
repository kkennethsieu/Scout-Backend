"""User response schema."""

from datetime import datetime

from pydantic import BaseModel


class UserResponse(BaseModel):
    uid: str
    email: str
    display_name: str
    photo_url: str | None
    created_at: datetime
    # Maintained atomically as the user creates/deletes reviews.
    review_count: int = 0
