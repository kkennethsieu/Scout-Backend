"""Config schema — public app configuration surfaced via GET /config."""

from pydantic import BaseModel


class ConfigResponse(BaseModel):
    """iOS version-gating config. Snake_case keys match the client's decoder."""

    ios_min_version: str
    ios_latest_version: str
    ios_update_url: str
