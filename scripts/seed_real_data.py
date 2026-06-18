"""Seed realistic data into the REAL Firestore, with REAL photos in Storage.

Spots, reviews, and users are written to Firestore and Firebase Auth. Photos are
genuine JPEGs: a pool of stock images is downloaded from picsum.photos, EXIF-
stripped via Pillow (mirroring app/services/storage_service.py), and uploaded as
real blobs to the Cloud Storage bucket — so photo_urls are real bucket URLs of
the same shape a live submission produces (storage.googleapis.com/<bucket>/...).

DANGER: This writes to your actual Firebase project AND uploads objects to your
real Storage bucket. Triple-check the project name before running.

Auth: uses gcloud Application Default Credentials by default. Run
`gcloud auth application-default login` once before using.
Optionally override with GOOGLE_APPLICATION_CREDENTIALS=<path-to-json>.

Usage:
    # With gcloud ADC (recommended for local dev):
    gcloud auth application-default login
    python -m scripts.seed_real_data --project scout-497021 --spots 8

    # Or with a service account file:
    GOOGLE_APPLICATION_CREDENTIALS=./service-account.json \\
      python -m scripts.seed_real_data --project scout-497021 --spots 8

The script refuses to run unless --project is exactly 'scout-497021' to
prevent accidental writes to the wrong project.
"""

import argparse
import json
import os
import random
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4

# Do NOT set FIRESTORE_EMULATOR_HOST here. We want real Firestore.
import firebase_admin
from firebase_admin import auth, credentials, firestore, storage
from PIL import Image

# The only project this script is allowed to touch.
ALLOWED_PROJECT = "scout-497021"
DEFAULT_BUCKET = "dev-scout-photos"

# A user the developer created manually in Firebase Auth for on-device testing.
# Seeded as a review author on every spot so there's always "my own" data to view.
PERSONAL_TEST_UID = "32WaqmcxZ2e6Zg5aGR9eMNvwokB2"

# Curated real spots with hand-authored, location-specific notes (see seed_spots.py).
from scripts.seed_spots import SEED_SPOTS  # noqa: E402

# Category content templates for auto-discovered spots (see spot_templates.py).
from scripts.spot_templates import DEFAULT_CATEGORY, TEMPLATES  # noqa: E402

DISCOVERED_PATH = os.path.join(os.path.dirname(__file__), "discovered_spots.json")

# Enum value pools — used by _mostly() to pick occasional off-mode values.
# Must match the API schema (app/schemas/review.py).
BEST_TIMES = ["Sunrise", "GoldenHour", "BlueHour", "Midday", "Night"]
ACCESS_LEVELS = ["Easy", "Moderate", "Difficult"]
CROWD_LEVELS = ["Empty", "Light", "Moderate", "Crowded"]
SEASONS = ["Spring", "Summer", "Fall", "Winter", "YearRound"]


# --- Aggregate logic (duplicated here to avoid pulling in the app package
#     which would try to init Firebase from env vars). Keep in sync with
#     app/services/aggregates.py. ---


def empty_aggregates() -> dict:
    return {
        "review_count": 0,
        "avg_rating": 0.0,
        "access_level_counts": {},
        "crowd_level_counts": {},
        "mode_access_level": None,
        "mode_crowd_level": None,
        "entrance_fee_sum": 0.0,
        "entrance_fee_n": 0,
        "avg_entrance_fee": None,
        "recent_review_photos": [],
        "best_time_of_day_counts": {},
        "best_times": [],
        "best_season_counts": {},
        "best_seasons": [],
        "permit_required_counts": {},
        "drone_allowed_counts": {},
        "tripod_allowed_counts": {},
        "mode_permit_required": None,
        "mode_drone_allowed": None,
        "mode_tripod_allowed": None,
        "recent_gear_recommendations": [],
        "recent_composition_hints": [],
    }


def _get_boolean_mode(counts: dict, tie_breaker: bool) -> bool | None:
    """Tristate majority vote. None when nobody answered; tie_breaker only for real ties."""
    true_count = counts.get("true", 0)
    false_count = counts.get("false", 0)
    if true_count == 0 and false_count == 0:
        return None
    if true_count == false_count:
        return tie_breaker
    return true_count > false_count


def update_or_init_aggregates(spot: dict, review: dict, review_id: str) -> dict:
    s = dict(spot)
    old_count = s.get("review_count", 0)
    old_avg = s.get("avg_rating", 0.0)
    new_count = old_count + 1
    s["review_count"] = new_count
    s["avg_rating"] = (old_avg * old_count + review["overall_rating"]) / new_count
    for field in ("access_level", "crowd_level"):
        v = review.get(field)
        if v is None:
            continue
        ck = f"{field}_counts"
        counts = dict(s.get(ck) or {})
        counts[v] = counts.get(v, 0) + 1
        s[ck] = counts
        s[f"mode_{field}"] = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    # entrance_fee running average (money number; 0 counts as free, None skipped)
    fee = review.get("entrance_fee")
    if fee is not None:
        s["entrance_fee_n"] = s.get("entrance_fee_n", 0) + 1
        s["entrance_fee_sum"] = s.get("entrance_fee_sum", 0.0) + fee
        s["avg_entrance_fee"] = round(s["entrance_fee_sum"] / s["entrance_fee_n"], 2)

    # best_time_of_day + best_season (multi-value) aggregation
    for field, list_key in (("best_time_of_day", "best_times"), ("best_season", "best_seasons")):
        ck = f"{field}_counts"
        counts = dict(s.get(ck) or {})
        for val in review.get(field) or []:
            counts[val] = counts.get(val, 0) + 1
        s[ck] = counts
        s[list_key] = [
            item[0]
            for item in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            if item[1] > 0
        ]

    # access & logistics tristate boolean aggregation (skip unanswered None)
    for field, tie_breaker in [
        ("permit_required", True),
        ("drone_allowed", False),
        ("tripod_allowed", False),
    ]:
        val = review.get(field)
        if val is None:
            continue
        counts_key = f"{field}_counts"
        counts = dict(s.get(counts_key) or {})
        val_str = "true" if val else "false"
        counts[val_str] = counts.get(val_str, 0) + 1
        s[counts_key] = counts
        s[f"mode_{field}"] = _get_boolean_mode(counts, tie_breaker)

    # gear & composition textual aggregates
    gear_tips = list(s.get("recent_gear_recommendations") or [])
    new_gear = review.get("gear_recommendations") or ""
    if new_gear.strip():
        gear_tips = [new_gear.strip()] + gear_tips
        s["recent_gear_recommendations"] = gear_tips[:5]

    comp_tips = list(s.get("recent_composition_hints") or [])
    new_comp = review.get("composition_hints") or ""
    if new_comp.strip():
        comp_tips = [new_comp.strip()] + comp_tips
        s["recent_composition_hints"] = comp_tips[:5]

    entry = {
        "review_id": review_id,
        "photo_url": review["photo_urls"][0],
        "created_at": review["created_at"],
    }
    s["recent_review_photos"] = ([entry] + (s.get("recent_review_photos") or []))[:5]
    return s


# --- Real photos: Unsplash search → download → EXIF-strip → Storage upload ---
#
# Only search calls (api.unsplash.com) count against the rate limit (50/hour on a
# demo key). Image-byte downloads (images.unsplash.com) are unlimited. We do one
# search per distinct query and reuse the resulting image pool across that spot's
# reviews, so total search calls == number of distinct spot queries.

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Pexels (API + image CDN) rejects the default python-urllib User-Agent with 403,
# so send a browser-like one on outbound photo requests.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
GEOCODE_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".geocode_cache.json")


def _require_geocoding_key() -> str:
    """Same key the app uses (Google Geocoding API), read from env or .env."""
    key = os.environ.get("GEOCODING_API_KEY")
    if not key:
        try:
            from dotenv import dotenv_values

            key = dotenv_values(".env").get("GEOCODING_API_KEY")
        except ImportError:
            pass
    if not key:
        sys.exit("[seed] GEOCODING_API_KEY is not set (needed to resolve real coordinates).")
    return key


def _geocode_components(result: dict) -> tuple[str, str, str]:
    """Pull (city, admin_area, country) from a Geocoding result — mirrors
    app/services/geocoding.py:_parse_components."""
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


def forward_geocode(query: str, key: str, cache: dict) -> dict | None:
    """Resolve a place name to real {lat, lng, city, admin_area, country}.

    Results are memoized in `cache` (persisted to .geocode_cache.json by main)
    so reruns don't re-call the API and coordinates stay stable.
    """
    if query in cache:
        return cache[query]
    params = urllib.parse.urlencode({"address": query, "key": key})
    try:
        with urllib.request.urlopen(f"{GEOCODE_URL}?{params}", timeout=15) as resp:
            body = json.load(resp)
    except Exception as e:
        print(f"[seed]   ! Geocode request failed for '{query}': {e}")
        return None
    if body.get("status") != "OK" or not body.get("results"):
        print(f"[seed]   ! Geocode returned {body.get('status')} for '{query}'")
        return None
    res = body["results"][0]
    loc = res["geometry"]["location"]
    city, admin, country = _geocode_components(res)
    resolved = {
        "lat": loc["lat"],
        "lng": loc["lng"],
        "city": city,
        "admin_area": admin,
        "country": country,
    }
    cache[query] = resolved
    return resolved

# Generic words in spot names that add noise to image search — dropped from the query.
_QUERY_STOPWORDS = {
    "overlook", "trail", "ridge", "lookout", "vista", "point", "steps", "curve",
    "archway", "base", "end", "top", "summit", "peak", "south", "north", "pull-off",
}


def _spot_query(name: str, city: str) -> str:
    """Build an Unsplash search query from a spot name + city.

    Strips a leading '#2'-style dedupe suffix and noisy generic words so the
    search keys on the real subject ('Griffith Observatory', 'Venice Canals').
    """
    base = name.split("#")[0].strip()
    words = [w for w in base.split() if w.lower() not in _QUERY_STOPWORDS]
    subject = " ".join(words) or base
    return f"{subject} {city}".strip()


def _require_unsplash_key() -> str:
    # Read ONLY the Unsplash key from .env — NOT load_dotenv(), which would also
    # pull the *_EMULATOR_HOST vars from .env into the process and redirect this
    # seeder at local emulators instead of real Firebase. A real shell env var
    # still wins over the .env value.
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        try:
            from dotenv import dotenv_values

            key = dotenv_values(".env").get("UNSPLASH_ACCESS_KEY")
        except ImportError:
            pass
    if not key:
        sys.exit(
            "[seed] UNSPLASH_ACCESS_KEY is not set.\n"
            "       Create a free Access Key at https://unsplash.com/developers, then add to .env:\n"
            "       UNSPLASH_ACCESS_KEY=<your-access-key>"
        )
    return key


def _get_pexels_key() -> str | None:
    """Optional second photo source. Returns the key or None (Unsplash-only)."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        try:
            from dotenv import dotenv_values

            key = dotenv_values(".env").get("PEXELS_API_KEY")
        except ImportError:
            pass
    return key


def pexels_search(query: str, per_page: int, key: str, page: int = 1) -> list[str]:
    """One Pexels search page → list of landscape image URLs (or [] on miss)."""
    params = urllib.parse.urlencode(
        {"query": query, "per_page": per_page, "page": page, "orientation": "landscape"}
    )
    req = urllib.request.Request(
        f"{PEXELS_SEARCH_URL}?{params}",
        headers={"Authorization": key, "User-Agent": BROWSER_UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"[seed]   ! Pexels search failed for '{query}': {e}")
        return []
    return [p["src"]["large"] for p in data.get("photos", [])]


def unsplash_search(query: str, per_page: int, key: str, page: int = 1) -> list[str]:
    """Return up to `per_page` landscape image URLs for the query (or [] on miss)."""
    params = urllib.parse.urlencode(
        {
            "query": query,
            "per_page": per_page,
            "page": page,
            "orientation": "landscape",
            "content_filter": "high",
        }
    )
    req = urllib.request.Request(
        f"{UNSPLASH_SEARCH_URL}?{params}",
        headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"[seed]   ! Unsplash search failed for '{query}': {e}")
        return []
    return [r["urls"]["regular"] for r in data.get("results", [])]


def _download_jpeg(url: str) -> bytes | None:
    """Download an image and re-encode as EXIF-free JPEG (mirrors storage_service)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        img = Image.open(BytesIO(raw)).convert("RGB")
        out = BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception as e:
        print(f"[seed]   ! Photo download failed ({url[:60]}...): {e}")
        return None


_UNSPLASH_PER_PAGE = 30  # Unsplash search max per page
_PEXELS_PER_PAGE = 50  # Pexels search max per page


def _collect_urls(search_fn, query: str, key: str, per_page: int, count: int, seen: set) -> list[str]:
    """Page one provider until it yields `count` new unique URLs (or runs dry)."""
    out: list[str] = []
    page = 1
    while len(out) < count and page <= 5:
        batch = search_fn(query, per_page, key, page=page)
        if not batch:
            break
        for u in batch:
            if u not in seen:
                seen.add(u)
                out.append(u)
        if len(batch) < per_page:
            break  # last page
        page += 1
    return out


def fetch_unique_images(
    query: str, count: int, unsplash_key: str, pexels_key: str | None = None
) -> list[bytes]:
    """Fetch `count` DISTINCT real JPEGs so no two reviews of a spot share a photo.

    Pulls from Pexels first (larger free quota) then tops up from Unsplash, so the
    tiny Unsplash hourly cap is conserved and the run survives one source being
    rate-limited. Returns however many it could get (possibly fewer than `count`)."""
    urls: list[str] = []
    seen: set[str] = set()
    if pexels_key:
        urls += _collect_urls(pexels_search, query, pexels_key, _PEXELS_PER_PAGE, count, seen)
    if len(urls) < count:
        need = count - len(urls)
        urls += _collect_urls(unsplash_search, query, unsplash_key, _UNSPLASH_PER_PAGE, need, seen)
    urls = urls[:count]
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_download_jpeg, urls))
    return [b for b in results if b]


def upload_review_photos(bucket, bucket_name: str, review_id: str, images: list[bytes]) -> list[str]:
    """Upload each image as its own blob under reviews/{review_id}/photos/ and
    return the public URLs (same shape as storage_service._public_url)."""

    def _upload(data: bytes) -> str:
        path = f"reviews/{review_id}/photos/{uuid4()}.jpg"
        bucket.blob(path).upload_from_string(data, content_type="image/jpeg")
        return f"https://storage.googleapis.com/{bucket_name}/{path}"

    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(_upload, images))


def _mostly(dominant: str, alternatives: list[str], p: float = 0.7) -> str:
    """Return the spot's dominant value most of the time, an alternative otherwise,
    so per-spot aggregates have a clear mode but aren't unrealistically unanimous."""
    if random.random() < p:
        return dominant
    return random.choice([a for a in alternatives if a != dominant] or alternatives)


def _mostly_bool(dominant: bool, p: float = 0.8) -> bool:
    return dominant if random.random() < p else (not dominant)


class _Bag:
    """Draws items without repeats, reshuffling when exhausted — keeps a spot's
    reviews from reusing the same note until the pool runs out."""

    def __init__(self, items: list[str]):
        self._items = list(items)
        self._pool: list[str] = []

    def draw(self) -> str:
        if not self._pool:
            self._pool = random.sample(self._items, len(self._items))
        return self._pool.pop()


def make_review(
    review_id: str,
    spot_id: str,
    spot_doc: dict,
    user_uid: str,
    created_at: datetime,
    photo_urls: list[str],
    cfg: dict,
    note: str,
    gear: str,
    comp: str,
):
    times = random.sample(cfg["best_times"], k=min(random.randint(1, 2), len(cfg["best_times"])))
    seasons = random.sample(
        cfg["best_seasons"], k=min(random.randint(1, 2), len(cfg["best_seasons"]))
    )
    return review_id, {
        "spot_id": spot_id,
        "spot_name": spot_doc["name"],
        "public_lat": spot_doc["public_lat"],
        "public_lng": spot_doc["public_lng"],
        "city": spot_doc["city"],
        "admin_area": spot_doc["admin_area"],
        "user_id": user_uid,
        "photo_urls": photo_urls,
        "overall_rating": random.choices([3, 4, 5], weights=cfg.get("rating_weights") or [1, 3, 4])[0],
        "notes": note,
        "best_time_of_day": times,
        "access_level": _mostly(cfg["access_level"], ACCESS_LEVELS),
        "entrance_fee": random.choice(cfg["entrance_fee_options"]),
        "crowd_level": _mostly(cfg["crowd_level"], CROWD_LEVELS),
        "best_season": seasons,
        "permit_required": _mostly_bool(cfg["permit"]),
        "drone_allowed": _mostly_bool(cfg["drone"]),
        "tripod_allowed": _mostly_bool(cfg["tripod"]),
        "gear_recommendations": gear,
        "composition_hints": comp,
        "created_at": created_at,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project", required=True, help=f"Firebase project ID (must be '{ALLOWED_PROJECT}')"
    )
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Cloud Storage bucket for photos")
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--spots", type=int, default=0, help="Cap total spots (0 = all)")
    parser.add_argument("--min-reviews", type=int, default=4)
    parser.add_argument("--max-reviews", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--with-discovered",
        action="store_true",
        help=f"Also seed auto-discovered spots from {os.path.basename(DISCOVERED_PATH)} "
        "(content resolved from spot_templates by category)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Only seed spots whose name isn't already in Firestore "
        "(top-up after a partial run, e.g. a photo rate-limit cutoff)",
    )
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    if args.project != ALLOWED_PROJECT:
        sys.exit(f"[seed] Refusing to run: --project must be '{ALLOWED_PROJECT}' (got '{args.project}').")

    # Hand-authored spots, plus auto-discovered ones if requested.
    spots_to_seed = list(SEED_SPOTS)
    if args.with_discovered:
        if not os.path.exists(DISCOVERED_PATH):
            sys.exit(f"[seed] --with-discovered set but {DISCOVERED_PATH} not found. "
                     "Run scripts.discover_spots first.")
        with open(DISCOVERED_PATH) as f:
            discovered = json.load(f)
        spots_to_seed += discovered
        print(f"[seed] Loaded {len(discovered)} discovered spots (+{len(SEED_SPOTS)} curated).")
    # Dedupe by name within this run. Curated spots come first so they win over any
    # same-named discovered spot. (--skip-existing only dedupes against names
    # already in Firestore, not collisions inside a single run.)
    seen_names: set[str] = set()
    deduped = []
    for c in spots_to_seed:
        if c["name"] in seen_names:
            continue
        seen_names.add(c["name"])
        deduped.append(c)
    if len(deduped) < len(spots_to_seed):
        print(f"[seed] Deduped {len(spots_to_seed) - len(deduped)} same-named spot(s).")
    spots_to_seed = deduped
    if args.spots:
        spots_to_seed = spots_to_seed[: args.spots]

    # Force REAL Firebase. Strip any emulator hosts (these are set in .env for
    # local dev and would otherwise redirect writes to dead local emulators).
    for var in ("FIRESTORE_EMULATOR_HOST", "FIREBASE_AUTH_EMULATOR_HOST", "STORAGE_EMULATOR_HOST"):
        if os.environ.pop(var, None):
            print(f"[seed] Ignoring {var} — writing to REAL Firebase.")

    unsplash_key = _require_unsplash_key()
    pexels_key = _get_pexels_key()  # optional second photo source
    geocoding_key = _require_geocoding_key()

    # Load the geocode cache so reruns don't re-call the Geocoding API.
    geocode_cache: dict = {}
    if os.path.exists(GEOCODE_CACHE_PATH):
        try:
            with open(GEOCODE_CACHE_PATH) as f:
                geocode_cache = json.load(f)
        except Exception:
            geocode_cache = {}

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    using_service_account = bool(cred_path and os.path.exists(cred_path))
    auth_method = f"service account: {cred_path}" if using_service_account else "gcloud ADC"

    sources = "Pexels + Unsplash" if pexels_key else "Unsplash only"
    if not args.yes:
        print(f"[seed] About to write seed data to REAL Firestore project: {args.project}")
        print(f"       Photos → REAL Storage bucket: {args.bucket} (sources: {sources})")
        print(f"       Auth: {auth_method}")
        print(f"       {len(spots_to_seed)} spots; ~{len(spots_to_seed)} photo searches "
              "per source (Unsplash demo 50/hr, Pexels 200/hr).")
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            sys.exit("[seed] Aborted.")

    random.seed(args.seed)

    # ---- Init Admin SDK against the real project (with Storage bucket) ----
    init_opts = {"projectId": args.project, "storageBucket": args.bucket}
    if using_service_account:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, init_opts)
    else:
        # Application Default Credentials from `gcloud auth application-default login`
        firebase_admin.initialize_app(options=init_opts)
    db = firestore.client()
    bucket = storage.bucket()

    now = datetime.now(timezone.utc)

    # ---- 1. Create users via Admin SDK (no passwords, no tokens) ----
    user_names = [
        "Alice Chen", "Bob Rivera", "Carol Kim", "Dana Patel", "Evan Wu",
        "Fiona Marsh", "Gabe Ortiz", "Hana Suzuki", "Ian Brooks", "Jada Nelson",
        "Kai Lawson", "Lena Volkov", "Mateo Reyes", "Nora Bennett", "Omar Haddad",
        "Priya Nair", "Quentin Lee", "Rosa Mendez", "Sam Whitfield", "Tara Okafor",
    ]
    users = []
    for i in range(args.users):
        display = user_names[i] if i < len(user_names) else f"Test User {i + 1}"
        # Stable, unique email even past the name pool, so reruns find the same user.
        email = f"seed-{display.split()[0].lower()}-{i}@example.com"
        try:
            user_record = auth.create_user(email=email, display_name=display)
            uid = user_record.uid
        except auth.EmailAlreadyExistsError:
            user_record = auth.get_user_by_email(email)
            uid = user_record.uid
        users.append({"uid": uid, "email": email, "display_name": display})

    # The developer's own pre-existing Auth user (not created here — just looked up
    # for its email/name). Added to the author pool and guaranteed a review per spot.
    try:
        rec = auth.get_user(PERSONAL_TEST_UID)
        personal_email = rec.email or "kenneth-test@example.com"
        personal_name = rec.display_name or "Kenneth (Test)"
    except Exception as e:
        print(f"[seed] Could not look up personal test user ({e}); using placeholders.")
        personal_email, personal_name = "kenneth-test@example.com", "Kenneth (Test)"
    personal_user = {"uid": PERSONAL_TEST_UID, "email": personal_email, "display_name": personal_name}
    users.append(personal_user)
    print(f"[seed] Created/found {len(users)} users in Firebase Auth (incl. personal test user).")

    # ---- 2. Write user docs (review_count filled in after reviews are generated) ----
    review_counts: dict[str, int] = {u["uid"]: 0 for u in users}

    # ---- 3. Generate spots and reviews from the curated real-spot list ----
    if args.skip_existing:
        existing_names = {s.to_dict().get("name") for s in db.collection("spots").stream()}
        before = len(spots_to_seed)
        spots_to_seed = [c for c in spots_to_seed if c["name"] not in existing_names]
        print(
            f"[seed] --skip-existing: {before - len(spots_to_seed)} already in Firestore, "
            f"{len(spots_to_seed)} to seed."
        )

    spot_ids = []
    total_reviews = 0
    for cfg in spots_to_seed:
        name = cfg["name"]

        # Coordinates: discovered spots already carry them (from Places); curated
        # spots are forward-geocoded (cached) from their geocode_query.
        if "lat" in cfg and "lng" in cfg:
            geo = {
                "lat": cfg["lat"],
                "lng": cfg["lng"],
                "city": cfg.get("city", ""),
                "admin_area": cfg.get("admin_area", ""),
                "country": cfg.get("country", "United States"),
            }
        else:
            geo = forward_geocode(cfg["geocode_query"], geocoding_key, geocode_cache)
            if not geo:
                print(f"[seed]   ! Could not geocode '{name}' — skipping.")
                continue

        # Resolve review text: curated spots bring their own notes; discovered spots
        # draw from the category templates with {name}/{city} woven in. `eff` carries
        # the tendency fields (best_times, access_level, ...) make_review reads.
        if "notes" in cfg:
            eff, notes, gear, comp = cfg, cfg["notes"], cfg["gear"], cfg["composition"]
        else:
            tpl = TEMPLATES.get(cfg.get("category"), TEMPLATES[DEFAULT_CATEGORY])
            eff = {**tpl, **cfg}
            city = geo["city"] or "California"
            notes = [s.format(name=name, city=city) for s in tpl["notes"]]
            gear = [s.format(name=name, city=city) for s in tpl["gear"]]
            comp = [s.format(name=name, city=city) for s in tpl["composition"]]
            # A real Google editorial summary (when --details was used) seeds one
            # genuinely accurate, spot-specific note.
            if cfg.get("description"):
                # Google editorial text can contain en/em dashes; strip them to
                # match the dash-free voice of the rest of the notes.
                desc = cfg["description"].replace("—", ", ").replace("–", ", ")
                notes = [desc] + notes

        # Decide the review set up front so we know exactly how many UNIQUE photos
        # to fetch — no image is ever shared between two reviews of this spot.
        # Distinct authors per spot (one review per user per spot, matching the API
        # rule); guarantee the personal test user is one of them.
        num_reviews = min(random.randint(args.min_reviews, args.max_reviews), len(users))
        authors = random.sample(users, num_reviews)
        if personal_user not in authors:
            authors[-1] = personal_user
        desired = [random.randint(1, 3) for _ in range(num_reviews)]

        # Fetch enough DISTINCT real photos for every review (override the search
        # with photo_query when the spot name alone returns too few).
        query = cfg.get("photo_query") or _spot_query(name, geo["city"])
        images = fetch_unique_images(query, sum(desired), unsplash_key, pexels_key)
        if not images:
            print(f"[seed]   ! No photos for '{query}' — skipping spot '{name}'.")
            continue

        # Every review gets at least one UNIQUE photo (never shared between reviews).
        # If Unsplash returned fewer images than planned reviews, trim the review
        # count rather than reuse a photo; spread any surplus as extra photos.
        effective = min(num_reviews, len(images))
        authors = authors[:effective]
        if personal_user not in authors and effective:
            authors[-1] = personal_user
        counts = [1] * effective
        extra = len(images) - effective
        for i in range(effective):
            if extra <= 0:
                break
            add = min(desired[i] - 1, extra)
            counts[i] += add
            extra -= add

        spot_id = str(uuid4())
        spot_ids.append(spot_id)
        spot_created = now - timedelta(days=random.randint(7, 90))
        spot_doc = {
            "name": name,
            "public_lat": geo["lat"],
            "public_lng": geo["lng"],
            "city": geo["city"],
            "admin_area": geo["admin_area"],
            "country": geo["country"],
            "created_at": spot_created,
            **empty_aggregates(),
        }
        print(
            f"[seed] '{name}' @ {geo['city']} ({geo['lat']:.4f},{geo['lng']:.4f}) "
            f"→ {effective} reviews, {sum(counts)} unique photos"
        )

        # Per-spot non-repeating draws for the resolved text fields.
        note_bag = _Bag(notes)
        gear_bag = _Bag(gear)
        comp_bag = _Bag(comp)

        review_offsets = sorted(
            random.uniform(0.5, (now - spot_created).total_seconds() / 86400.0)
            for _ in range(effective)
        )
        reviews = []
        img_idx = 0  # hand out disjoint slices of the unique-image pool
        for author, offset_days, want in zip(authors, review_offsets, counts):
            chosen = images[img_idx : img_idx + want]
            img_idx += want
            created_at = spot_created + timedelta(days=offset_days)
            review_id = str(uuid4())
            photo_urls = upload_review_photos(bucket, args.bucket, review_id, chosen)
            _, review = make_review(
                review_id, spot_id, spot_doc, author["uid"], created_at, photo_urls,
                eff, note_bag.draw(), gear_bag.draw(), comp_bag.draw(),
            )
            reviews.append((review_id, review))
            review_counts[author["uid"]] += 1
            spot_doc = update_or_init_aggregates(spot_doc, review, review_id)

        batch = db.batch()
        batch.set(db.collection("spots").document(spot_id), spot_doc)
        for rid, review in reviews:
            batch.set(db.collection("reviews").document(rid), review)
        batch.commit()
        total_reviews += len(reviews)

    # Persist the geocode cache for future reruns.
    try:
        with open(GEOCODE_CACHE_PATH, "w") as f:
            json.dump(geocode_cache, f, indent=2)
    except Exception as e:
        print(f"[seed] (could not save geocode cache: {e})")

    # ---- 4. Write user docs now that review_count is known ----
    user_batch = db.batch()
    for u in users:
        user_batch.set(
            db.collection("users").document(u["uid"]),
            {
                "id": u["uid"],
                "email": u["email"],
                "display_name": u["display_name"],
                "photo_url": None,
                "created_at": now,
                "review_count": review_counts[u["uid"]],
                "home_city": "Los Angeles",
                "home_country": "United States",
            },
        )
    user_batch.commit()

    print(f"[seed] Wrote {len(spot_ids)} spots, {total_reviews} reviews to {args.project}.")

    print("\n=== Seed summary ===")
    print(f"Project: {args.project}")
    print(f"Spots seeded: {len(spot_ids)} / {len(spots_to_seed)} curated")
    print("\nUsers (created in Firebase Auth — sign in from iOS to get a real ID token):")
    for u in users:
        print(f"  - {u['email']}  uid={u['uid']}")
    print("\nSample spot IDs:")
    for sid in spot_ids[:3]:
        print(f"  - {sid}")


if __name__ == "__main__":
    main()
