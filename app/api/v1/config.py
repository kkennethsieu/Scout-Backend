"""Config endpoint — public app configuration (iOS version gating)."""

from fastapi import APIRouter, Depends

from app.api.v1.deps import rate_limit_ip
from app.core.config import settings
from app.schemas.config import ConfigResponse

router = APIRouter(tags=["config"])


@router.get(
    "/config",
    response_model=ConfigResponse,
    dependencies=[Depends(rate_limit_ip("60/minute", scope="get_config"))],
)
async def get_config() -> ConfigResponse:
    """Publish iOS version-gating config.

    Public and unauthenticated (like /legal) — the client hits this on launch and
    fails open, so it must work with no auth. The client compares its build against
    these versions to gate/nudge updates.
    """
    return ConfigResponse(
        ios_min_version=settings.IOS_MIN_VERSION,
        ios_latest_version=settings.IOS_LATEST_VERSION,
        ios_update_url=settings.IOS_UPDATE_URL,
    )
