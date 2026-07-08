"""Reverse geocoding via Google Geocoding API.

Async httpx client. Called during POST /spots/with-review to get
city/admin_area/country from lat/lng.
"""

import httpx

from app.core.config import settings
from app.core.exceptions import GeocodingFailed, GeocodingNoLocation


async def reverse(lat: float, lng: float) -> dict:
    """
    Reverse-geocode (lat, lng) to {city, admin_area, country}.

    Raises GeocodingFailed on HTTP errors or non-OK status from Google.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"latlng": f"{lat},{lng}", "key": settings.GEOCODING_API_KEY},
        )
        if r.status_code != 200:
            raise GeocodingFailed(f"HTTP {r.status_code}")
        body = r.json()
        if body.get("status") != "OK":
            raise GeocodingFailed(body.get("status", "unknown"))
        components = _parse_components(body)
        # Only a coordinate with no resolvable country (open ocean, Null Island)
        # is truly unusable — reject that as non-retryable. A missing *city* is
        # common for the remote spots this app is built around (trailheads,
        # overlooks, coastline), so fall back to the finest available area name
        # (state, then country) rather than rejecting the submission.
        if not components["country"]:
            raise GeocodingNoLocation()
        if not components["city"]:
            components["city"] = components["admin_area"] or components["country"]
        return components


def _parse_components(body: dict) -> dict:
    """
    Collect city/admin/country candidates across ALL geocoding results.

    Google returns results ordered most-specific → least-specific. For a remote
    coordinate with no nearby street address the first result is often a bare
    Plus Code with no address_components, while the locality/county/state/country
    live in later results — so we must scan every result, not just results[0].

    City preference: locality > sublocality > postal_town > county
    (administrative_area_level_2). County is the last resort so remote spots
    still resolve to a meaningful name like "Santa Barbara County" instead of
    empty. The first (most-specific) occurrence of each type wins, which also
    avoids the ordering bug where sublocality before locality would win.
    """
    candidates = {
        "locality": "",
        "sublocality": "",
        "postal_town": "",
        "administrative_area_level_2": "",
    }
    admin = ""
    country = ""

    for result in body.get("results") or []:
        for c in result.get("address_components", []):
            types = c.get("types", [])
            for key in candidates:
                if key in types and not candidates[key]:
                    candidates[key] = c["long_name"]
            if "administrative_area_level_1" in types and not admin:
                admin = c["long_name"]
            if "country" in types and not country:
                country = c["long_name"]

    city = (
        candidates["locality"]
        or candidates["sublocality"]
        or candidates["postal_town"]
        or candidates["administrative_area_level_2"]
    )
    return {"city": city, "admin_area": admin, "country": country}
