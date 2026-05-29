"""Review endpoints — single review fetch."""

from fastapi import APIRouter, Depends

from app.api.v1.deps import current_uid
from app.schemas.review import ReviewResponse
from app.services import review_service

router = APIRouter(tags=["reviews"])


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    uid: str = Depends(current_uid),
):
    """Get a single review by ID."""
    return await review_service.get_review(review_id)
