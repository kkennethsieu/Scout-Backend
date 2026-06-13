"""Legal schema — links to the hosted privacy policy and terms of service."""

from pydantic import BaseModel


class LegalLinksResponse(BaseModel):
    """Public links the client renders (e.g. in a settings/sign-up screen)."""

    privacy_policy_url: str
    terms_of_service_url: str
    # ISO date the documents were last revised — lets the client surface "updated".
    updated_at: str
