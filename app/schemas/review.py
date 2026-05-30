"""Review response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.spot import SpotResponse


class ReviewResponse(BaseModel):
    id: str
    spot_id: str
    user_id: str
    photo_urls: list[str]
    overall_rating: int
    notes: str
    best_time_of_day: list[str]
    access_level: str
    entrance_fee: str
    crowd_level: str
    environment: str
    gear_recommendations: Optional[str] = ""
    composition_hints: Optional[str] = ""
    permit_required: bool = False
    drone_allowed: bool = False
    tripod_allowed: bool = False
    created_at: datetime


class SubmitReviewWithNewSpotResponse(BaseModel):
    spot: SpotResponse
    review: ReviewResponse
