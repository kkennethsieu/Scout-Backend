"""Spot service — nearby query and single-spot fetch."""

from app.core.exceptions import SpotNotFound
from app.core.firebase import db
from app.services.geo import bounding_box, haversine_km


async def find_nearby(lat: float, lng: float, radius_km: float, limit: int) -> list[dict]:
    """
    Returns spots within radius_km of (lat,lng), sorted by distance, capped at `limit`.

    INVARIANT: Correct only when total spots in the latitude band is small
    relative to `limit * 3`. Firestore's range filter on public_lat orders
    by latitude, so over-fetching limit*3 then re-sorting by distance is a
    heuristic — at high density, the closest spots could sort late by
    latitude and get cut. Fine at <100 spots. Swap to geohashing when this
    breaks.
    """
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)

    query = (
        db.collection("spots")
        .where("public_lat", ">=", min_lat)
        .where("public_lat", "<=", max_lat)
        .limit(limit * 3)
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

    candidates.sort(key=lambda s: s["_distance_km"])
    return candidates[:limit]


async def get_spot(spot_id: str) -> dict:
    """Fetch a single spot by ID. Raises SpotNotFound if missing."""
    ref = db.collection("spots").document(spot_id)
    snap = ref.get()
    if not snap.exists:
        raise SpotNotFound()
    data = snap.to_dict()
    data["id"] = snap.id
    return data
