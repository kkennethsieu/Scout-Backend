"""Legal endpoint — public links to the privacy policy and terms of service.

Intentionally unauthenticated: the client shows these on sign-up / pre-login
screens, and the documents themselves are public. Reads the URLs from settings
so they can be repointed (e.g. to a custom domain) without a code change.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.legal import LegalLinksResponse

router = APIRouter(tags=["legal"])


@router.get("/legal", response_model=LegalLinksResponse)
async def get_legal_links() -> LegalLinksResponse:
    """Return links to the hosted privacy policy and terms of service."""
    return LegalLinksResponse(
        privacy_policy_url=settings.PRIVACY_POLICY_URL,
        terms_of_service_url=settings.TERMS_OF_SERVICE_URL,
        updated_at=settings.LEGAL_UPDATED_AT,
    )
