"""User endpoints — current user profile and reviews."""

from fastapi import APIRouter, Depends, Query, Response

from app.api.v1.deps import current_uid, verify_token
from app.schemas.pagination import PaginatedReviews
from app.schemas.user import UserResponse, UserUpdate
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


@router.patch("/users/me", response_model=UserResponse)
async def update_current_user(
    updates: UserUpdate,
    claims: dict = Depends(verify_token),
):
    """
    Update the caller's own profile (home_city / home_country).

    PATCH semantics — only fields present in the body are changed; a blank
    value clears that field. Uses verify_token (not current_uid) so the doc
    can be created from claims if it doesn't exist yet.
    """
    uid = claims["uid"]
    return await user_service.update_user(uid, claims, updates.model_dump(exclude_unset=True))


@router.delete("/users/me", status_code=204)
async def delete_current_user(
    uid: str = Depends(current_uid),
):
    """
    Delete the caller's account.

    Anonymizes their reviews (kept as community content), hard-deletes their user
    doc, and deletes the Firebase Auth user server-side — avoiding the client-side
    requiresRecentLogin re-auth. The client signs out locally after this returns.
    """
    await user_service.delete_account(uid)
    return Response(status_code=204)


@router.get("/users/me/reviews", response_model=PaginatedReviews)
async def get_my_reviews(
    limit: int = Query(10, ge=1, le=25),
    cursor: str | None = Query(None),
    uid: str = Depends(current_uid),
):
    """Current user's reviews, paginated, newest first."""
    return await review_service.get_reviews_for_user(uid, limit, cursor)
