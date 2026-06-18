"""Auto-discover real photography spots across California via Google Places.

Runs Places Text Search for each category query (see spot_templates.CATEGORY_
QUERIES) biased to a set of anchor locations (big CA metros + iconic nature),
dedupes by place_id, reverse-geocodes each hit for city/admin/country, tags it
with its category, and writes scripts/discovered_spots.json for review.

The seeder (scripts/seed_real_data.py) then consumes that JSON alongside the
hand-authored seed_spots.py, resolving review text from spot_templates by
category. Coordinates come straight from Places, so no forward geocoding needed.

Requires the Places API enabled in GCP and GEOCODING_API_KEY (the key must allow
both Places + Geocoding). Read-only against Google; writes only the local JSON.

  COST: Places Text Search is billed (~$0.032/request). This runs roughly
  (anchors * queries) requests. Output is cached to JSON — don't re-run casually.

Usage:
    python -m scripts.discover_spots                 # full statewide run
    python -m scripts.discover_spots --max-per-query 4 --target 250
    python -m scripts.discover_spots --anchors "Los Angeles,San Francisco"
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from scripts.spot_templates import CATEGORY_PHOTO_QUERY, CATEGORY_QUERIES

PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Place `types` that mean "not a photography spot" — fuzzy search drags these in
# (a restaurant named "The Overlook"), so drop them unless a strong-attraction
# type is also present. This is the main fix for category misclassification.
JUNK_TYPES = {
    "restaurant", "food", "cafe", "bar", "lodging", "store", "supermarket",
    "shopping_mall", "gym", "school", "hospital", "bank", "gas_station",
    "car_repair", "real_estate_agency", "lawyer", "doctor", "dentist", "pharmacy",
    "convenience_store", "clothing_store", "night_club", "spa", "parking",
}
STRONG_TYPES = {"tourist_attraction", "natural_feature", "park"}

# Name patterns for administrative / business / access-point listings that Places
# returns but aren't photo spots (offices, departments, marinas-as-businesses,
# trailheads, parking, rec centers). Filtered by name regardless of types.
NAME_JUNK = re.compile(
    r"(department|division|\binc\.?\b|corporation|\bllc\b|apartments|headquarters|"
    r"recreation center|rec center|harbor office|wharfinger|\boffice\b|"
    r"parks ?& ?recreation|parks and recreation|watersports|rentals|"
    r"fish and wildlife|chamber of commerce|ranger station|light and power|"
    r"trailhead|trail head|\bparking\b|\blot\b|\bcenter\b|\bcentre\b)",
    re.I,
)


def is_real_spot(name: str, types: list[str]) -> bool:
    """Keep only places that look like actual photo spots."""
    if name and NAME_JUNK.search(name):
        return False
    t = set(types)
    if t & STRONG_TYPES:
        return True
    return not (t & JUNK_TYPES)


def refine_category(default_cat: str, types: list[str], name: str) -> str:
    """Sharpen the query-derived category using Google's place `types` + name."""
    t = set(types)
    nl = name.lower()
    if "natural_feature" in t or any(w in nl for w in ("beach", "cove", "shore")):
        if any(w in nl for w in ("beach", "cove", "shore")):
            return "beach"
        if any(w in nl for w in ("lake", "reservoir", "pond")):
            return "lake"
        if any(w in nl for w in ("fall", "creek", "canyon", "trail", "peak", "mountain")):
            return "trail_waterfall"
    if "marina" in t or "harbor" in nl or "marina" in nl:
        return "harbor"
    if t & {"church", "place_of_worship", "museum", "library", "city_hall"}:
        return "architecture"
    if "art_gallery" in t:
        return "mural_street"
    return default_cat


def crowd_from_popularity(n: int | None) -> str | None:
    """Map Google review count to a crowd tendency (popularity proxy)."""
    if not n:
        return None
    if n >= 3000:
        return "Crowded"
    if n >= 600:
        return "Moderate"
    return "Light"


def rating_weights(rating: float | None) -> list[int] | None:
    """Bias seeded review ratings toward the spot's real Google rating ([3,4,5])."""
    if not rating:
        return None
    if rating >= 4.6:
        return [1, 3, 6]
    if rating >= 4.2:
        return [1, 4, 4]
    if rating >= 3.8:
        return [2, 4, 3]
    return [3, 3, 2]


def place_details(place_id: str, key: str) -> dict:
    """Fetch editorial summary + opening hours for one place (billed)."""
    params = urllib.parse.urlencode(
        {"place_id": place_id, "fields": "editorial_summary,opening_hours", "key": key}
    )
    try:
        with urllib.request.urlopen(f"{DETAILS_URL}?{params}", timeout=15) as resp:
            return (json.load(resp) or {}).get("result", {}) or {}
    except Exception:
        return {}


def _closes_before_dark(opening_hours: dict) -> bool:
    """True if every listed day closes by 19:00 (so Night shooting isn't viable)."""
    periods = opening_hours.get("periods") or []
    if not periods:
        return False
    closes = [p["close"]["time"] for p in periods if p.get("close", {}).get("time")]
    return bool(closes) and all(c <= "1900" for c in closes)
OUT_PATH = os.path.join(os.path.dirname(__file__), "discovered_spots.json")
REV_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".reverse_geocode_cache.json")

# Anchor points: major CA metros + iconic photography regions. Text Search is
# location-biased, so this set is how "all of California" is actually covered.
ANCHORS = {
    "Los Angeles": (34.0522, -118.2437),
    "San Diego": (32.7157, -117.1611),
    "San Francisco": (37.7749, -122.4194),
    "San Jose": (37.3382, -121.8863),
    "Sacramento": (38.5816, -121.4944),
    "Oakland": (37.8044, -122.2712),
    "Long Beach": (33.7701, -118.1937),
    "Santa Barbara": (34.4208, -119.6982),
    "Fresno": (36.7378, -119.7871),
    "Monterey": (36.6002, -121.8947),
    "Santa Cruz": (36.9741, -122.0308),
    "Palm Springs": (33.8303, -116.5453),
    "South Lake Tahoe": (38.9399, -119.9772),
    "Yosemite Valley": (37.7456, -119.5936),
    "Big Sur": (36.2704, -121.8081),
    "Joshua Tree": (33.8734, -115.9010),
    "Death Valley": (36.5054, -117.0794),
    "Eureka": (40.8021, -124.1637),
    "Mendocino": (39.3076, -123.7995),
    "Napa": (38.2975, -122.2869),
}


def _require_key() -> str:
    key = os.environ.get("GEOCODING_API_KEY")
    if not key:
        try:
            from dotenv import dotenv_values

            key = dotenv_values(".env").get("GEOCODING_API_KEY")
        except ImportError:
            pass
    if not key:
        sys.exit("[discover] GEOCODING_API_KEY not set (needs Places + Geocoding access).")
    return key


def places_text_search(query: str, lat: float, lng: float, radius_m: int, key: str) -> list[dict]:
    """One Text Search request, location-biased to (lat,lng). Returns raw results."""
    params = urllib.parse.urlencode(
        {"query": query, "location": f"{lat},{lng}", "radius": radius_m, "key": key}
    )
    try:
        with urllib.request.urlopen(f"{PLACES_URL}?{params}", timeout=20) as resp:
            body = json.load(resp)
    except Exception as e:
        print(f"[discover]   ! Places request failed for '{query}': {e}")
        return []
    status = body.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        # REQUEST_DENIED usually means the Places API isn't enabled or the key is
        # restricted — surface it loudly since every query would fail the same way.
        print(f"[discover]   ! Places status {status} for '{query}': {body.get('error_message','')}")
    return body.get("results", [])


def _reverse_components(result: dict) -> tuple[str, str, str]:
    candidates = {"locality": "", "sublocality": "", "postal_town": ""}
    admin = country = ""
    for c in result.get("address_components", []):
        types = c.get("types", [])
        for key in candidates:
            if key in types:
                candidates[key] = c["long_name"]
        if "administrative_area_level_1" in types:
            admin = c["long_name"]
        if "country" in types:
            country = c["long_name"]
    city = candidates["locality"] or candidates["sublocality"] or candidates["postal_town"]
    return city, admin, country


def reverse_geocode(lat: float, lng: float, key: str, cache: dict) -> dict | None:
    ckey = f"{lat:.5f},{lng:.5f}"
    if ckey in cache:
        return cache[ckey]
    params = urllib.parse.urlencode({"latlng": f"{lat},{lng}", "key": key})
    try:
        with urllib.request.urlopen(f"{GEOCODE_URL}?{params}", timeout=15) as resp:
            body = json.load(resp)
    except Exception as e:
        print(f"[discover]   ! Reverse geocode failed for {ckey}: {e}")
        return None
    if body.get("status") != "OK" or not body.get("results"):
        return None
    city, admin, country = _reverse_components(body["results"][0])
    resolved = {"city": city, "admin_area": admin, "country": country}
    cache[ckey] = resolved
    return resolved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-query", type=int, default=5, help="Top N results per query")
    parser.add_argument("--radius-km", type=float, default=40.0, help="Search bias radius")
    parser.add_argument("--target", type=int, default=0, help="Stop after this many spots (0=all)")
    parser.add_argument("--anchors", default="", help="Comma-separated subset of anchor names")
    parser.add_argument(
        "--details",
        action="store_true",
        help="Also fetch Place Details per spot (real description + hours). Extra cost.",
    )
    parser.add_argument("--out", default=OUT_PATH)
    args = parser.parse_args()

    key = _require_key()
    radius_m = int(args.radius_km * 1000)

    anchors = ANCHORS
    if args.anchors:
        wanted = {a.strip() for a in args.anchors.split(",")}
        anchors = {k: v for k, v in ANCHORS.items() if k in wanted}
        missing = wanted - set(anchors)
        if missing:
            print(f"[discover] Unknown anchors ignored: {missing}")

    cache: dict = {}
    if os.path.exists(REV_CACHE_PATH):
        try:
            with open(REV_CACHE_PATH) as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    seen_place_ids: set[str] = set()
    spots: list[dict] = []
    n_requests = 0

    for anchor_name, (lat, lng) in anchors.items():
        print(f"[discover] Anchor: {anchor_name}")
        for category, queries in CATEGORY_QUERIES.items():
            for q in queries:
                results = places_text_search(q, lat, lng, radius_m, key)
                n_requests += 1
                for r in results[: args.max_per_query]:
                    pid = r.get("place_id")
                    if not pid or pid in seen_place_ids:
                        continue
                    name = r.get("name")
                    types = r.get("types", [])
                    if not is_real_spot(name or "", types):
                        continue  # drop restaurants/hotels/stores/offices/trailheads
                    loc = (r.get("geometry") or {}).get("location") or {}
                    if "lat" not in loc or "lng" not in loc:
                        continue
                    geo = reverse_geocode(loc["lat"], loc["lng"], key, cache)
                    if not geo or not geo["city"] or geo["country"] != "United States":
                        continue  # skip unresolved or out-of-country hits
                    seen_place_ids.add(pid)

                    cat = refine_category(category, types, name or "")
                    entry = {
                        "name": name,
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "city": geo["city"],
                        "admin_area": geo["admin_area"],
                        "country": geo["country"],
                        "category": cat,
                        "photo_query": f"{CATEGORY_PHOTO_QUERY[cat]} {geo['city']}",
                    }
                    # Grounding from the search result itself (no extra API cost).
                    crowd = crowd_from_popularity(r.get("user_ratings_total"))
                    if crowd:
                        entry["crowd_level"] = crowd
                    weights = rating_weights(r.get("rating"))
                    if weights:
                        entry["rating_weights"] = weights

                    # Optional richer grounding via Place Details (billed).
                    if args.details:
                        d = place_details(pid, key)
                        summary = (d.get("editorial_summary") or {}).get("overview")
                        if summary:
                            entry["description"] = summary
                        if _closes_before_dark(d.get("opening_hours") or {}):
                            entry["best_times"] = ["GoldenHour", "Sunrise", "Midday"]
                        time.sleep(0.05)

                    spots.append(entry)
                time.sleep(0.1)  # be gentle on the API
                if args.target and len(spots) >= args.target:
                    break
            if args.target and len(spots) >= args.target:
                break
        if args.target and len(spots) >= args.target:
            break

    # Persist caches + output.
    try:
        with open(REV_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"[discover] (could not save reverse-geocode cache: {e})")

    with open(args.out, "w") as f:
        json.dump(spots, f, indent=2)

    by_cat: dict[str, int] = {}
    by_admin: dict[str, int] = {}
    for s in spots:
        by_cat[s["category"]] = by_cat.get(s["category"], 0) + 1
        by_admin[s["admin_area"]] = by_admin.get(s["admin_area"], 0) + 1
    print(f"\n[discover] {len(spots)} unique spots from {n_requests} Places requests.")
    print(f"[discover] By category: {by_cat}")
    print(f"[discover] By state: {by_admin}")
    print(f"[discover] Wrote {args.out} — review/trim it, then run the seeder.")


if __name__ == "__main__":
    main()
