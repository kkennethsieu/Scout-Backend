"""Spot response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator


class RecentReviewPhoto(BaseModel):
    review_id: str
    photo_url: str
    created_at: datetime


class SpotResponse(BaseModel):
    id: str
    name: str
    public_lat: float
    public_lng: float
    city: str
    admin_area: str
    country: str
    created_at: datetime
    review_count: int
    avg_rating: float
    recent_review_photos: list[RecentReviewPhoto] = []
    mode_access_level: str
    mode_entrance_fee: str
    mode_crowd_level: str
    mode_environment: str
    best_times: list[str] = []
    mode_permit_required: Optional[bool] = None
    mode_drone_allowed: Optional[bool] = None
    mode_tripod_allowed: Optional[bool] = None
    recent_gear_recommendations: list[str] = []
    recent_composition_hints: list[str] = []


class SpotSummaryResponse(BaseModel):
    id: str
    name: str
    public_lat: float
    public_lng: float
    city: str
    admin_area: str
    country: str
    created_at: datetime
    review_count: int
    avg_rating: float
    cover_photo_url: Optional[str] = None
    recent_review_photos: list[RecentReviewPhoto] = []
    best_times: list[str] = []
    mode_permit_required: Optional[bool] = None
    mode_drone_allowed: Optional[bool] = None
    mode_tripod_allowed: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_cover_photo(cls, data):
        if isinstance(data, dict):
            if not data.get("cover_photo_url"):
                photos = data.get("recent_review_photos")
                if photos and isinstance(photos, list):
                    first = photos[0]
                    if isinstance(first, dict):
                        data["cover_photo_url"] = first.get("photo_url")
                    elif hasattr(first, "photo_url"):
                        data["cover_photo_url"] = first.photo_url
        return data
