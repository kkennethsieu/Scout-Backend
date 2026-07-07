"""Spot service — nearby query, name search, and single-spot fetch."""

import base64
import binascii

from google.cloud.firestore_v1.field_path import FieldPath

from app.core.config import settings
from app.core.exceptions import InvalidCursor, SpotNotFound
from app.core.firebase import db
from app.services import spot_cache
from app.services.geo import bounding_box, haversine_km

# Firestore caps an `in` filter at 30 values.
_IN_QUERY_LIMIT = 30


def _encode_cursor(distance_km: float, spot_id: str) -> str:
    """Opaque cursor for the distance-sorted nearby results.

    Results are sorted by distance (not a Firestore-indexed field), so the
    doc-id `start_after` cursor used by the review endpoints can't be reused.
    We encode the last item's (distance, id) instead.
    """
    raw = f"{distance_km:.6f}|{spot_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(cursor: str) -> tuple[float, str]:
    """Decode an opaque nearby cursor back to (distance_km, spot_id).

    Raises InvalidCursor on any malformed input.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        distance_str, spot_id = raw.split("|", 1)
        return float(distance_str), spot_id
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise InvalidCursor()


async def find_nearby(
    lat: float,
    lng: float,
    radius_km: float,
    limit: int,
    cursor: str | None = None,
) -> dict:
    """Nearby spots with an empty-result fallback to a predefined flagship location.

    Runs the real distance scan first. If it returns spots — or the caller is
    paging (cursor present) — that's the answer, flagged is_fallback=False. Only
    when the FIRST page is completely empty (and the fallback is enabled) do we
    re-scan around settings.FALLBACK_LAT/LNG so the client always has something to
    render. The fallback is a single page (next_cursor=None): its distances are
    measured from the flagship center, so replaying that cursor against the
    caller's real coordinates would be meaningless.
    """
    result = await _scan_nearby(lat, lng, radius_km, limit, cursor)

    if result["items"] or cursor is not None or not settings.NEARBY_FALLBACK_ENABLED:
        return {**result, "is_fallback": False}

    fb = await _scan_nearby(
        settings.FALLBACK_LAT, settings.FALLBACK_LNG, settings.FALLBACK_RADIUS_KM, limit, None
    )
    return {"items": fb["items"], "limit": limit, "next_cursor": None, "is_fallback": True}


async def _scan_nearby(
    lat: float,
    lng: float,
    radius_km: float,
    limit: int,
    cursor: str | None = None,
) -> dict:
    """
    Returns spots within radius_km of (lat,lng), sorted by distance, paginated.

    Shape: {"items": [...], "limit": limit, "next_cursor": str | None}.

    INVARIANT: Scans the full spots snapshot (served from spot_cache), computes
    haversine distance, filters by radius, and sorts in memory. Fine at <100
    spots; swap to geohashing / an external index when the collection outgrows an
    in-memory scan.

    Pagination uses an opaque (distance, id) cursor — see _encode_cursor — since
    the result order is by distance rather than a Firestore-indexed field.
    Distance is kept in a tuple alongside the spot (never written into the spot
    dict) so the shared cached dicts stay un-mutated.
    """
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    spots = await spot_cache.get_all_spots()

    candidates = []  # (distance_km, id, spot)
    for s in spots:
        if not (min_lat <= s["public_lat"] <= max_lat):
            continue
        if not (min_lng <= s["public_lng"] <= max_lng):
            continue
        d = haversine_km(lat, lng, s["public_lat"], s["public_lng"])
        if d <= radius_km:
            candidates.append((d, s["id"], s))

    # Sort by distance, then id as a stable tiebreak so the cursor is unambiguous.
    candidates.sort(key=lambda c: (c[0], c[1]))

    # Apply cursor: keep only candidates strictly after the (distance, id) pair.
    if cursor:
        after_d, after_id = _decode_cursor(cursor)
        candidates = [c for c in candidates if (c[0], c[1]) > (after_d, after_id)]

    page = candidates[:limit]
    next_cursor = _encode_cursor(page[-1][0], page[-1][1]) if len(candidates) > limit else None

    return {"items": [c[2] for c in page], "limit": limit, "next_cursor": next_cursor}


def _name_rank(name_lower: str, q: str) -> int:
    """Match quality for ranking: 0 exact, 1 prefix, 2 substring (lower = better)."""
    if name_lower == q:
        return 0
    if name_lower.startswith(q):
        return 1
    return 2


async def search_by_name(q: str, limit: int) -> list[dict]:
    """
    Search spots by name, case-insensitive substring match ("fall" → "Horsetail Fall").

    Ranked exact > prefix > substring, tie-broken by review_count (desc) then name.
    Global (not geo-scoped) — a direct name hit jumps straight to the spot.

    Scans the full spots snapshot (served from spot_cache): fine at <100 spots.
    The scale path is a denormalized name_lower field with Firestore range queries
    for prefix, or an external search index (Algolia/Typesense) for true substring
    at volume.
    """
    q = q.strip().lower()
    if not q:
        return []

    spots = await spot_cache.get_all_spots()

    matches = []
    for s in spots:
        name_lower = (s.get("name") or "").lower()
        if not name_lower:
            continue
        if q in name_lower:
            matches.append((_name_rank(name_lower, q), s))

    matches.sort(key=lambda m: (m[0], -m[1].get("review_count", 0), m[1]["name"]))
    return [s for _, s in matches[:limit]]


async def get_spot(spot_id: str) -> dict:
    """Fetch a single spot by ID. Raises SpotNotFound if missing."""
    ref = db.collection("spots").document(spot_id)
    snap = ref.get()
    if not snap.exists:
        raise SpotNotFound()
    data = snap.to_dict()
    data["id"] = snap.id
    return data


def get_spots_by_ids(ids: list[str]) -> dict[str, dict]:
    """Batch-resolve spot ids to spot dicts. Returns {id: spot} for the ids that
    still exist (a spot is deleted when its last review is removed, so some ids
    in a saved list may resolve to nothing — those are simply omitted).

    Chunks ids into Firestore's 30-value `in` limit. Synchronous (Firestore SDK
    is sync); callers wrap it in asyncio.to_thread if they're on the hot path.
    """
    found: dict[str, dict] = {}
    if not ids:
        return found
    col = db.collection("spots")
    for start in range(0, len(ids), _IN_QUERY_LIMIT):
        chunk = ids[start : start + _IN_QUERY_LIMIT]
        for doc in col.where(FieldPath.document_id(), "in", chunk).stream():
            data = doc.to_dict()
            data["id"] = doc.id
            found[doc.id] = data
    return found
