"""Review schemas — Base / Create / Response split.

ReviewBase holds the client-supplied content (constrained vocabularies + limits).
ReviewCreate is the multipart request body for submitting against an existing spot
(photos travel separately as UploadFiles). SpotWithReviewCreate adds the new-spot
fields. ReviewResponse adds server-generated fields (id, user_id, created_at, ...).

Optionality contract: every field is optional except overall_rating. A missing
value means "the submitter didn't answer" — distinct from a `False`/empty answer.
The tristate booleans (permit_required, drone_allowed, tripod_allowed) capture
exactly that distinction.
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import UploadFile
from pydantic import BaseModel, Field, field_validator

from app.schemas.enums import AccessLevel, BestTimeOfDay, CrowdLevel, Season
from app.schemas.spot import SpotResponse

TEXT_MAX = 2000
FEE_MAX = 100000  # upper guard ($) against garbage input


class ReviewBase(BaseModel):
    """Client-supplied review content. Only overall_rating is required."""

    overall_rating: int = Field(..., ge=1, le=5)
    notes: Optional[str] = Field(None, max_length=TEXT_MAX)
    best_time_of_day: list[BestTimeOfDay] = []
    best_season: list[Season] = []
    access_level: Optional[AccessLevel] = None
    # Money: USD amount per person. 0 = free (confirmed); None = not answered.
    entrance_fee: Optional[float] = Field(None, ge=0, le=FEE_MAX)
    crowd_level: Optional[CrowdLevel] = None
    # Tristate: True / False / None(unanswered) are three distinct answers.
    permit_required: Optional[bool] = None
    drone_allowed: Optional[bool] = None
    tripod_allowed: Optional[bool] = None
    gear_recommendations: Optional[str] = Field(None, max_length=TEXT_MAX)
    composition_hints: Optional[str] = Field(None, max_length=TEXT_MAX)

    @field_validator("entrance_fee", mode="before")
    @classmethod
    def _blank_fee_to_none(cls, v):
        """A blank/whitespace form value means "didn't answer" (None) — not 0/free."""
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("entrance_fee", mode="after")
    @classmethod
    def _quantize_fee(cls, v: Optional[float]) -> Optional[float]:
        """Round money to 2 decimal places (cents). Stored as a number; iOS formats it."""
        if v is None:
            return v
        return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# Fields that live on the create models but never on the persisted review doc.
# model_dump(exclude=...) strips them before the review is written to Firestore.
_CREATE_ONLY_FIELDS = {"photos"}
_SPOT_ONLY_FIELDS = {"name", "lat", "lng"}


class ReviewCreate(ReviewBase):
    """Multipart request body for POST /spots/{id}/reviews.

    Photos ride inside the model so the whole body binds as flat form fields
    (FastAPI supports UploadFile inside a Form model). Count is enforced in the
    service via validate_photo_count() to keep the PHOTO_COUNT_INVALID code.
    """

    photos: list[UploadFile]


class SpotWithReviewCreate(ReviewCreate):
    """Multipart request body for POST /spots/with-review — adds the new spot's fields."""

    name: str = Field(..., min_length=1, max_length=200)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class ReviewResponse(ReviewBase):
    """A persisted review, including server-generated fields."""

    id: str
    spot_id: str
    user_id: str
    photo_urls: list[str] = Field(..., min_length=1, max_length=10)
    created_at: datetime


class SubmitReviewWithNewSpotResponse(BaseModel):
    spot: SpotResponse
    review: ReviewResponse
