"""Spot endpoints — nearby query, single spot, and submission routes."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.v1.deps import current_uid
from app.schemas.enums import validate_enum, validate_enum_list
from app.schemas.pagination import PaginatedReviews
from app.schemas.review import ReviewResponse, SubmitReviewWithNewSpotResponse
from app.schemas.spot import SpotResponse, SpotSummaryResponse
from app.services import geocoding, review_service, spot_service

router = APIRouter(tags=["spots"])


@router.get("/spots", response_model=list[SpotSummaryResponse])
async def list_nearby_spots(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(..., gt=0, le=100),
    limit: int = Query(20, ge=1, le=50),
    uid: str = Depends(current_uid),
):
    """List spots within radius_km of (lat, lng), sorted by distance."""
    spots = await spot_service.find_nearby(lat, lng, radius_km, limit)
    return spots


@router.get("/spots/{spot_id}", response_model=SpotResponse)
async def get_spot(
    spot_id: str,
    uid: str = Depends(current_uid),
):
    """Get a single spot with full aggregates."""
    return await spot_service.get_spot(spot_id)


@router.get("/spots/{spot_id}/reviews", response_model=PaginatedReviews)
async def get_spot_reviews(
    spot_id: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    uid: str = Depends(current_uid),
):
    """Paginated reviews for a spot, newest first."""
    return await review_service.get_reviews_for_spot(spot_id, limit, cursor)


@router.post("/spots/{spot_id}/reviews", response_model=ReviewResponse, status_code=201)
async def submit_review(
    spot_id: str,
    photos: list[UploadFile] = File(...),
    overall_rating: int = Form(..., ge=1, le=5),
    notes: str = Form(..., min_length=1, max_length=1000),
    best_time_of_day: list[str] = Form(...),
    access_level: str = Form(...),
    entrance_fee: str = Form(...),
    crowd_level: str = Form(...),
    environment: str = Form(...),
    uid: str = Depends(current_uid),
):
    """
    Submit a review for an existing spot (multipart).

    Photos: repeated key, one part per file, JPEG only, ≤10MB each, 1–5 total.
    best_time_of_day: repeated key.
    All enums: exact capitalized strings ("Easy", not "easy").
    """
    # Validate enums explicitly — FastAPI Form doesn't enforce Literal types
    validate_enum("access_level", access_level)
    validate_enum("entrance_fee", entrance_fee)
    validate_enum("crowd_level", crowd_level)
    validate_enum("environment", environment)
    validate_enum_list("best_time_of_day", best_time_of_day)

    return await review_service.submit_review(
        spot_id=spot_id,
        photos=photos,
        overall_rating=overall_rating,
        notes=notes,
        best_time_of_day=best_time_of_day,
        access_level=access_level,
        entrance_fee=entrance_fee,
        crowd_level=crowd_level,
        environment=environment,
        uid=uid,
    )


@router.post(
    "/spots/with-review",
    response_model=SubmitReviewWithNewSpotResponse,
    status_code=201,
)
async def submit_with_new_spot(
    photos: list[UploadFile] = File(...),
    name: str = Form(..., min_length=1, max_length=200),
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    overall_rating: int = Form(..., ge=1, le=5),
    notes: str = Form(..., min_length=1, max_length=1000),
    best_time_of_day: list[str] = Form(...),
    access_level: str = Form(...),
    entrance_fee: str = Form(...),
    crowd_level: str = Form(...),
    environment: str = Form(...),
    uid: str = Depends(current_uid),
):
    """
    Create a new spot + first review in one request (multipart).

    Reverse-geocodes lat/lng for city/admin_area/country.
    Geocoding failure → 503 GEOCODING_FAILED (nothing uploaded yet).
    """
    # Validate enums
    validate_enum("access_level", access_level)
    validate_enum("entrance_fee", entrance_fee)
    validate_enum("crowd_level", crowd_level)
    validate_enum("environment", environment)
    validate_enum_list("best_time_of_day", best_time_of_day)

    # Reverse-geocode BEFORE uploading photos — fail fast
    geo_data = await geocoding.reverse(lat, lng)

    return await review_service.submit_with_new_spot(
        photos=photos,
        name=name,
        lat=lat,
        lng=lng,
        overall_rating=overall_rating,
        notes=notes,
        best_time_of_day=best_time_of_day,
        access_level=access_level,
        entrance_fee=entrance_fee,
        crowd_level=crowd_level,
        environment=environment,
        uid=uid,
        geo_data=geo_data,
    )
