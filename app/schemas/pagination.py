"""Pagination schemas for list endpoints."""

from pydantic import BaseModel

from app.schemas.review import ReviewResponse
from app.schemas.spot import SpotSummaryResponse


class PaginatedReviews(BaseModel):
    items: list[ReviewResponse]
    limit: int
    next_cursor: str | None


class PaginatedSpots(BaseModel):
    items: list[SpotSummaryResponse]
    limit: int
    next_cursor: str | None
