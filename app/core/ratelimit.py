"""Per-user rate limiting.

A FastAPI dependency factory that throttles a route by the caller's Firebase uid.

NOTE: storage is in-process (per Cloud Run instance). With N instances the
effective limit is up to N× the configured value, so this guards against a single
abusive user, not for exact global quotas. Swap MemoryStorage for a shared backend
(e.g. RedisStorage on Memorystore) when exact limits are needed — the dependency
signature stays the same.
"""

import time

from fastapi import Depends
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.core.exceptions import RateLimited
from app.core.security import current_uid

_storage = MemoryStorage()
_limiter = MovingWindowRateLimiter(_storage)


def rate_limit(limit: str, scope: str):
    """Build a dependency that allows at most `limit` (e.g. "10/minute") requests
    per uid within `scope`. Each scope is an isolated bucket, so limits on
    different routes don't share a counter."""
    item = parse(limit)

    async def dependency(uid: str = Depends(current_uid)) -> None:
        if not _limiter.hit(item, scope, uid):
            stats = _limiter.get_window_stats(item, scope, uid)
            retry_after = max(1, int(stats.reset_time - time.time()))
            raise RateLimited(retry_after)

    return dependency
