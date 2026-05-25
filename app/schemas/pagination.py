"""Pagination schemas for review list endpoints."""

from pydantic import BaseModel

from app.schemas.review import ReviewResponse


class PaginatedReviews(BaseModel):
    items: list[ReviewResponse]
    limit: int
    next_cursor: str | None
