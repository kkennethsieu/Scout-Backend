"""Review endpoints — single review fetch + delete."""

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.api.v1.deps import current_uid, rate_limit, rate_limit_ip, verify_app_check
from app.schemas.review import ReviewResponse, ReviewUpdate
from app.services import review_service, summary_service

router = APIRouter(tags=["reviews"], dependencies=[Depends(verify_app_check)])


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewResponse,
    dependencies=[Depends(rate_limit_ip("120/minute", scope="get_review"))],
)
async def get_review(
    review_id: str,
):
    """Get a single review by ID.

    Public: no JWT required (App Check still applies at the router level).
    """
    return await review_service.get_review(review_id)


@router.patch(
    "/reviews/{review_id}",
    response_model=ReviewResponse,
    dependencies=[Depends(rate_limit("20/minute", scope="edit_review"))],
)
async def edit_review(
    review_id: str,
    body: ReviewUpdate,
    background_tasks: BackgroundTasks,
    uid: str = Depends(current_uid),
):
    """Edit one of the caller's own reviews (content fields only, JSON body).

    PATCH semantics: only fields present in the body change; omit a field to leave
    it untouched, send an explicit null / [] to clear it. Photos aren't editable
    here. 404 if missing, 403 if it isn't the caller's review.
    """
    patch = body.model_dump(exclude_unset=True)
    review, spot_id = await review_service.edit_review(review_id, patch, uid)
    # Content changed → the spot's AI summary may be stale; refresh off the request
    # path (debounced inside the service, so most edits are a cheap no-op).
    background_tasks.add_task(summary_service.maybe_regenerate_summary, spot_id)
    return review


@router.delete(
    "/reviews/{review_id}",
    status_code=204,
    dependencies=[Depends(rate_limit("30/minute", scope="delete_review"))],
)
async def delete_review(
    review_id: str,
    background_tasks: BackgroundTasks,
    uid: str = Depends(current_uid),
):
    """Delete one of the caller's own reviews.

    Reverses the review's effect on the spot's aggregates and the author's
    review_count. 404 if missing, 403 if it isn't the caller's review.
    """
    spot_id = await review_service.delete_review(review_id, uid)
    # If the spot survived (still has reviews), refresh its AI summary off the
    # request path. None means the spot was deleted with its last review.
    background_tasks.add_task(summary_service.maybe_regenerate_summary, spot_id)
    return Response(status_code=204)
