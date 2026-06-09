"""User endpoints — current user profile and reviews."""

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import current_uid, verify_token
from app.schemas.pagination import PaginatedReviews
from app.schemas.user import UserResponse
from app.services import review_service, user_service

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserResponse)
async def get_current_user(
    claims: dict = Depends(verify_token),
):
    """
    Get current user profile. Creates user doc on first hit (read-through).

    Uses verify_token directly (not current_uid) because it needs
    email/name/picture from the full claims dict.
    """
    uid = claims["uid"]
    return await user_service.get_or_create_user(uid, claims)


@router.get("/users/me/reviews", response_model=PaginatedReviews)
async def get_my_reviews(
    limit: int = Query(10, ge=1, le=25),
    cursor: str | None = Query(None),
    uid: str = Depends(current_uid),
):
    """Current user's reviews, paginated, newest first."""
    return await review_service.get_reviews_for_user(uid, limit, cursor)
