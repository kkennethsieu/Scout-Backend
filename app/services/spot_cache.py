"""In-process TTL cache of the spots collection.

find_nearby and search_by_name both scan the whole spots collection. Rather than
read every spot from Firestore on each request, we cache the full snapshot in
process for a short TTL and serve both scans from it.

Per-instance and eventually consistent: a write may take up to
SPOT_CACHE_TTL_SECONDS to appear on instances that didn't take it. The instance
that took the write calls invalidate() and reflects it immediately. This trade is
acceptable — spot data changes infrequently and a short lag is fine.

Callers treat the returned list and dicts as READ-ONLY (they're shared across
requests). Response serialization only reads them, so handing out references is
safe; mutating them would corrupt the cache.
"""

import asyncio
import time

from app.core.config import settings
from app.core.firebase import db

_lock = asyncio.Lock()
_cache: list[dict] | None = None
_expires_at: float = 0.0


def _read_all_spots() -> list[dict]:
    """Synchronous full-collection read. Run via asyncio.to_thread."""
    spots = []
    for doc in db.collection("spots").stream():
        s = doc.to_dict()
        s["id"] = doc.id
        spots.append(s)
    return spots


async def get_all_spots() -> list[dict]:
    """Return the cached spots snapshot, refreshing it if missing or expired.

    A single asyncio.Lock + double-check guards against a cache stampede — under
    concurrent misses only one coroutine reads Firestore; the rest reuse the
    snapshot it produces.
    """
    global _cache, _expires_at

    if _cache is not None and time.monotonic() < _expires_at:
        return _cache

    async with _lock:
        # Re-check: another coroutine may have refreshed while we waited.
        if _cache is not None and time.monotonic() < _expires_at:
            return _cache
        spots = await asyncio.to_thread(_read_all_spots)
        _cache = spots
        _expires_at = time.monotonic() + settings.SPOT_CACHE_TTL_SECONDS
        return _cache


def invalidate() -> None:
    """Drop the cached snapshot so the next read refreshes from Firestore.

    Called after writes on this instance; other instances catch up via the TTL.
    """
    global _cache, _expires_at
    _cache = None
    _expires_at = 0.0
