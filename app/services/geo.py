"""Geographic math utilities — haversine distance and bounding box.

Pure functions, no Firebase dependency. Safe for unit testing.
"""

import math

# Earth radius in km (mean radius)
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula. Returns distance in kilometers.
    Accurate for all distances; slightly imprecise near antipodes
    (use Vincenty if sub-meter precision needed — not needed here).
    """
    lat1_r, lng1_r = math.radians(lat1), math.radians(lng1)
    lat2_r, lng2_r = math.radians(lat2), math.radians(lng2)

    dlat = lat2_r - lat1_r
    dlng = lng2_r - lng1_r

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """
    Calculate a bounding box (min_lat, max_lat, min_lng, max_lng) for a circle
    of `radius_km` centered at (lat, lng).

    NOTE: This is a simple approximation that breaks near the poles and
    the ±180° meridian. Fine for the continental US and most inhabited areas.
    At high latitudes, the longitude range expands correctly via the cos(lat)
    divisor, but the formula doesn't handle wrapping.

    Returns (min_lat, max_lat, min_lng, max_lng) in decimal degrees.
    """
    # 1 degree of latitude ≈ 111.32 km
    lat_delta = radius_km / 111.32

    # 1 degree of longitude varies by latitude
    lng_delta = radius_km / (111.32 * math.cos(math.radians(lat)))

    min_lat = lat - lat_delta
    max_lat = lat + lat_delta
    min_lng = lng - lng_delta
    max_lng = lng + lng_delta

    return min_lat, max_lat, min_lng, max_lng
