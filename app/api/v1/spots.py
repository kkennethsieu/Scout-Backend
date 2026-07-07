"""Spot endpoints — nearby query, single spot, and submission routes."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query

from app.api.v1.deps import current_uid, rate_limit, rate_limit_ip, verify_app_check
from app.schemas.enums import ReviewSort
from app.schemas.pagination import PaginatedReviews, PaginatedSpots
from app.schemas.review import (
    ReviewCreate,
    ReviewResponse,
    SpotWithReviewCreate,
    SubmitReviewWithNewSpotResponse,
)
from app.schemas.spot import SpotResponse, SpotSummaryResponse
from app.services import geocoding, review_service, spot_service, summary_service

router = APIRouter(tags=["spots"], dependencies=[Depends(verify_app_check)])


@router.get(
    "/spots",
    response_model=PaginatedSpots,
    dependencies=[Depends(rate_limit_ip("120/minute", scope="list_spots"))],
)
async def list_nearby_spots(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(..., gt=0, le=1000),
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
):
    """List spots within radius_km of (lat, lng), sorted by distance, paginated.

    Public: no JWT required (App Check still applies at the router level).

    If the first page finds nothing nearby, the response falls back to spots around
    a predefined flagship location with `is_fallback=true` (a single page), so the
    client can render something and label it instead of showing a blank map.
    """
    radius_km = min(radius_km, 500)
    return await spot_service.find_nearby(lat, lng, radius_km, limit, cursor)


@router.get(
    "/spots/search",
    response_model=list[SpotSummaryResponse],
    dependencies=[Depends(rate_limit_ip("30/minute", scope="search_spots"))],
)
async def search_spots(
    q: str = Query(..., min_length=2, max_length=50),
    limit: int = Query(5, ge=1, le=10),
):
    """Search spots by name (case-insensitive substring), ranked by match quality.

    Global — not geo-scoped. Powers the "Spots" section of the search bar; the
    "Places" section is resolved client-side via MKLocalSearch.

    Public: no JWT required (App Check still applies at the router level).
    """
    return await spot_service.search_by_name(q, limit)


@router.get(
    "/spots/{spot_id}",
    response_model=SpotResponse,
    dependencies=[Depends(rate_limit_ip("120/minute", scope="get_spot"))],
)
async def get_spot(
    spot_id: str,
):
    """Get a single spot with full aggregates.

    Public: no JWT required (App Check still applies at the router level).
    """
    return await spot_service.get_spot(spot_id)


@router.get(
    "/spots/{spot_id}/reviews",
    response_model=PaginatedReviews,
    dependencies=[Depends(rate_limit_ip("120/minute", scope="get_spot_reviews"))],
)
async def get_spot_reviews(
    spot_id: str,
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    sort: ReviewSort = Query("newest"),
):
    """Paginated reviews for a spot. `sort`: newest | highest_rated | lowest_rated | scout.

    Public: no JWT required (App Check still applies at the router level).
    """
    return await review_service.get_reviews_for_spot(spot_id, limit, cursor, sort)


@router.get(
    "/spots/{spot_id}/reviews/search",
    response_model=PaginatedReviews,
    dependencies=[Depends(rate_limit_ip("30/minute", scope="search_spot_reviews"))],
)
async def search_spot_reviews(
    spot_id: str,
    q: str = Query(..., min_length=2, max_length=50),
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    sort: ReviewSort = Query("newest"),
):
    """Search a spot's reviews by review text (notes / gear / composition).

    `sort`: newest | highest_rated | lowest_rated | scout (default newest).

    Public: no JWT required (App Check still applies at the router level).
    """
    return await review_service.search_reviews_for_spot(spot_id, q, limit, cursor, sort)


@router.post(
    "/spots/{spot_id}/reviews",
    response_model=ReviewResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("10/minute", scope="submit_review"))],
)
async def submit_review(
    spot_id: str,
    data: Annotated[ReviewCreate, Form()],
    background_tasks: BackgroundTasks,
    uid: str = Depends(current_uid),
):
    """
    Submit a review for an existing spot (multipart).

    Photos: repeated `photos` key, one part per file, JPEG only, ≤10MB each, 1–5 total.
    All content fields except overall_rating are optional; enums are validated by
    the ReviewCreate model (exact capitalized strings, e.g. "Easy" not "easy").
    """
    review = await review_service.submit_review(spot_id=spot_id, data=data, uid=uid)
    # The spot gained a review — refresh its AI summary off the request path
    # (debounced inside the service, so most submits are a cheap no-op).
    background_tasks.add_task(summary_service.maybe_regenerate_summary, spot_id)
    return review


@router.post(
    "/spots/with-review",
    response_model=SubmitReviewWithNewSpotResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("10/minute", scope="submit_with_new_spot"))],
)
async def submit_with_new_spot(
    data: Annotated[SpotWithReviewCreate, Form()],
    uid: str = Depends(current_uid),
):
    """
    Create a new spot + first review in one request (multipart).

    Reverse-geocodes lat/lng for city/admin_area/country.
    Geocoding failure → 503 GEOCODING_FAILED (nothing uploaded yet).
    """
    # Reverse-geocode BEFORE uploading photos — fail fast
    geo_data = await geocoding.reverse(data.lat, data.lng)

    return await review_service.submit_with_new_spot(data=data, uid=uid, geo_data=geo_data)
