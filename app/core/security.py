"""Authentication dependencies for FastAPI endpoints."""

import logging

from fastapi import Depends, Header
from firebase_admin import auth

from app.core.exceptions import InvalidToken, MissingToken

log = logging.getLogger(__name__)


async def verify_token(authorization: str | None = Header(default=None)) -> dict:
    """
    Verify Firebase ID token from the Authorization header.

    Returns full decoded claims dict. Use current_uid() if you only need the uid.

    Header(default=None) is critical — without it, missing-header requests get
    a FastAPI 422 before our handler runs. With default=None, we route through
    our 401 MissingToken instead.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise MissingToken()

    token = authorization[7:]
    try:
        return auth.verify_id_token(token, check_revoked=False)
    except Exception as e:
        # Sanitize: Firebase errors can include email claims. Strip after 'email":'.
        msg = str(e).split('email":', 1)[0]
        log.warning("token verification failed: %s", msg)
        raise InvalidToken()


async def current_uid(claims: dict = Depends(verify_token)) -> str:
    """
    Extract uid from verified token claims.

    Default dependency for endpoints that only need the uid.
    /users/me uses verify_token directly because it needs email/name/picture
    from claims.
    """
    return claims["uid"]
