"""Per-user rate limiting.

A FastAPI dependency factory that throttles a route by the caller's Firebase uid.

NOTE: storage is in-process (per Cloud Run instance). With N instances the
effective limit is up to N× the configured value, so this guards against a single
abusive user, not for exact global quotas. Swap MemoryStorage for a shared backend
(e.g. RedisStorage on Memorystore) when exact limits are needed — the dependency
signature stays the same.
"""

import time

from fastapi import Depends, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.core.exceptions import RateLimited
from app.core.security import current_uid

_storage = MemoryStorage()
_limiter = MovingWindowRateLimiter(_storage)


def _enforce(item, scope: str, identity: str) -> None:
    """Consume one token for (scope, identity); raise RateLimited if exhausted."""
    if not _limiter.hit(item, scope, identity):
        stats = _limiter.get_window_stats(item, scope, identity)
        retry_after = max(1, int(stats.reset_time - time.time()))
        raise RateLimited(retry_after)


def _client_ip(request: Request) -> str:
    """Best-effort caller IP for keying unauthenticated limits.

    On Cloud Run the caller sits behind Google's front end, so request.client.host
    is the proxy; the original client is the first entry of X-Forwarded-For. XFF is
    client-spoofable, but this limiter only guards against a single abusive caller
    (see module note), so best-effort keying is acceptable.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(limit: str, scope: str):
    """Build a dependency that allows at most `limit` (e.g. "10/minute") requests
    per uid within `scope`. Each scope is an isolated bucket, so limits on
    different routes don't share a counter."""
    item = parse(limit)

    async def dependency(uid: str = Depends(current_uid)) -> None:
        _enforce(item, scope, uid)

    return dependency


def rate_limit_ip(limit: str, scope: str):
    """Like rate_limit, but keyed by caller IP instead of uid — for public
    (unauthenticated) routes where no uid is available."""
    item = parse(limit)

    async def dependency(request: Request) -> None:
        _enforce(item, scope, _client_ip(request))

    return dependency
