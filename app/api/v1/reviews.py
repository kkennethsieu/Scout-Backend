"""Review endpoints — single review fetch + delete."""

from fastapi import APIRouter, Depends, Response

from app.api.v1.deps import current_uid, rate_limit, verify_app_check
from app.schemas.review import ReviewResponse
from app.services import review_service

router = APIRouter(tags=["reviews"], dependencies=[Depends(verify_app_check)])


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    uid: str = Depends(current_uid),
):
    """Get a single review by ID."""
    return await review_service.get_review(review_id)


@router.delete(
    "/reviews/{review_id}",
    status_code=204,
    dependencies=[Depends(rate_limit("30/minute", scope="delete_review"))],
)
async def delete_review(
    review_id: str,
    uid: str = Depends(current_uid),
):
    """Delete one of the caller's own reviews.

    Reverses the review's effect on the spot's aggregates and the author's
    review_count. 404 if missing, 403 if it isn't the caller's review.
    """
    await review_service.delete_review(review_id, uid)
    return Response(status_code=204)
