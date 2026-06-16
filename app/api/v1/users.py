"""User endpoints — current user profile and reviews."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Response

from app.api.v1.deps import current_uid, rate_limit, verify_app_check, verify_token
from app.schemas.pagination import PaginatedReviews
from app.schemas.user import UserResponse, UserUpdate
from app.services import review_service, storage_service, user_service

router = APIRouter(tags=["users"], dependencies=[Depends(verify_app_check)])


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


@router.patch(
    "/users/me",
    response_model=UserResponse,
    dependencies=[Depends(rate_limit("20/minute", scope="update_user"))],
)
async def update_current_user(
    body: Annotated[UserUpdate, Form()],
    claims: dict = Depends(verify_token),
):
    """
    Update the caller's own profile (multipart/form-data).

    Editable: display_name, home_city, home_country, email_notifications,
    push_notifications, and an optional profile `photo`. email is read-only (the
    Firebase Auth identity). PATCH semantics — only fields the client sends are
    changed; a blank home_city/home_country clears it. Uses verify_token (not
    current_uid) so the doc can be created from claims if it doesn't exist yet.
    """
    uid = claims["uid"]
    updates = body.to_update_dict()

    new_photo_path: str | None = None
    if body.photo is not None:
        photo_url, new_photo_path = await storage_service.upload_avatar(uid, body.photo)
        updates["photo_url"] = photo_url

    try:
        result = await user_service.update_user(uid, claims, updates)
    except Exception:
        # Profile write failed after the avatar uploaded — don't orphan the blob.
        if new_photo_path is not None:
            await storage_service.cleanup([new_photo_path])
        raise

    # New avatar persisted — prune the user's previous avatar(s).
    if new_photo_path is not None:
        await storage_service.delete_avatar_blobs(uid, keep_path=new_photo_path)

    return result


@router.delete(
    "/users/me",
    status_code=204,
    dependencies=[Depends(rate_limit("10/minute", scope="delete_user"))],
)
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
