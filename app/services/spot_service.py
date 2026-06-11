"""Spot service — nearby query, name search, and single-spot fetch."""

import base64
import binascii

from app.core.exceptions import InvalidCursor, SpotNotFound
from app.core.firebase import db
from app.services.geo import bounding_box, haversine_km

# Safety cap on how many docs the nearby query scans from the latitude band.
# At current scale (<100 spots) the whole band fits well under this; it only
# guards against an unbounded scan. Swap to geohashing when this is the limit.
_NEARBY_BAND_CAP = 500


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
    """
    Returns spots within radius_km of (lat,lng), sorted by distance, paginated.

    Shape: {"items": [...], "limit": limit, "next_cursor": str | None}.

    INVARIANT: Correct only while the total spots in the latitude band stays
    under `_NEARBY_BAND_CAP`. Firestore's range filter on public_lat can't
    order by distance, so we scan the whole band, compute haversine distance,
    filter by radius, and sort in memory. Fine at <100 spots. Swap to
    geohashing when the band exceeds the cap.

    Pagination uses an opaque (distance, id) cursor — see _encode_cursor — since
    the result order is by distance rather than a Firestore-indexed field.
    """
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)

    query = (
        db.collection("spots")
        .where("public_lat", ">=", min_lat)
        .where("public_lat", "<=", max_lat)
        .limit(_NEARBY_BAND_CAP)
    )

    candidates = []
    for doc in query.stream():
        s = doc.to_dict()
        if not (min_lng <= s["public_lng"] <= max_lng):
            continue
        d = haversine_km(lat, lng, s["public_lat"], s["public_lng"])
        if d <= radius_km:
            s["id"] = doc.id
            s["_distance_km"] = d
            candidates.append(s)

    # Sort by distance, then id as a stable tiebreak so the cursor is unambiguous.
    candidates.sort(key=lambda s: (s["_distance_km"], s["id"]))

    # Apply cursor: keep only candidates strictly after the (distance, id) pair.
    if cursor:
        after_d, after_id = _decode_cursor(cursor)
        candidates = [s for s in candidates if (s["_distance_km"], s["id"]) > (after_d, after_id)]

    page = candidates[:limit]
    next_cursor = (
        _encode_cursor(page[-1]["_distance_km"], page[-1]["id"])
        if len(candidates) > limit
        else None
    )

    # Drop the internal distance key — not part of the response schema.
    for s in page:
        s.pop("_distance_km", None)

    return {"items": page, "limit": limit, "next_cursor": next_cursor}


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

    Same in-memory streaming model as find_nearby: fine at <100 spots. The scale
    path is a normalized name field with Firestore prefix queries, or an external
    search index (Algolia/Typesense) for true substring at volume.
    """
    q = q.strip().lower()
    if not q:
        return []

    matches = []
    for doc in db.collection("spots").stream():
        s = doc.to_dict()
        name_lower = s["name"].lower()
        if q in name_lower:
            s["id"] = doc.id
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
