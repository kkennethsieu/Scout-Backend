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
    # True when `items` are not near the requested point but around a predefined
    # flagship location, returned because the real nearby query was empty. Lets the
    # client label them ("No spots near you — here are some popular ones"). Always
    # False for the list-spots endpoint, which never falls back.
    is_fallback: bool = False
