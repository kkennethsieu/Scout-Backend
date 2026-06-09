"""Seed FAKE data into the REAL Firestore (dev environment only).

DANGER: This writes to your actual Firebase project. Triple-check the
project name before running.

Auth: uses gcloud Application Default Credentials by default. Run
`gcloud auth application-default login` once before using.
Optionally override with GOOGLE_APPLICATION_CREDENTIALS=<path-to-json>.

Usage:
    # With gcloud ADC (recommended for local dev):
    gcloud auth application-default login
    python -m scripts.seed_real_db --project scout-dev --spots 8

    # Or with a service account file:
    GOOGLE_APPLICATION_CREDENTIALS=./scout-dev-service-account.json \\
      python -m scripts.seed_real_db --project scout-dev --spots 8

The script refuses to run unless --project starts with 'scout-dev' to
prevent accidental prod writes.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Do NOT set FIRESTORE_EMULATOR_HOST here. We want real Firestore.
import firebase_admin
from firebase_admin import auth, credentials, firestore

DEFAULT_CENTER_LAT = 34.0522
DEFAULT_CENTER_LNG = -118.2437

SPOT_NAMES = [
    "Griffith Observatory Overlook",
    "Echo Park Lake Bridge",
    "Vista Hermosa Sunset",
    "Sixth Street Viaduct",
    "Hollywood Sign Trail",
    "Venice Canals South",
    "Baldwin Hills Scenic",
    "Angels Flight Steps",
    "Mulholland Pull-Off",
    "Kenneth Hahn Ridge",
    "El Matador Cove",
    "Point Dume Bluff",
    "Runyon Canyon Peak",
    "Downtown Rooftop North",
    "Silver Lake Reservoir",
]

NOTES_POOL = [
    "Soft light right before sunset, sparse foot traffic on weekdays.",
    "Bring a wide lens — the skyline barely fits at 24mm full frame.",
    "Lot fills up fast on weekends; arrive at least an hour before golden hour.",
    "Marine layer can roll in unexpectedly even in summer. Check the webcam first.",
    "Gate locks at 10pm sharp. Rangers do enforce it.",
    "The hike is steeper than it looks on the map. Wear real shoes.",
    "Shoulder of the road is narrow — park on the south side only.",
    "Tripods are tolerated but security will ask you to leave if you block the path.",
]

BEST_TIMES = ["Sunrise", "GoldenHour", "BlueHour", "Midday", "Night"]
ACCESS_LEVELS = ["Easy", "Moderate", "Difficult"]
# entrance_fee is now a USD number (0 = free). Mostly-free pool for realism.
ENTRANCE_FEES = [0.0, 0.0, 0.0, 0.0, 10.00, 15.00, 25.00, 35.00]
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


def jittered_coord(center_lat: float, center_lng: float, max_km: float):
    import math

    dlat_km = random.uniform(-max_km, max_km)
    dlng_km = random.uniform(-max_km, max_km)
    dlat = dlat_km / 111.0
    dlng = dlng_km / (111.0 * math.cos(math.radians(center_lat)))
    return center_lat + dlat, center_lng + dlng


GEAR_POOL = [
    "Wide-angle lens (14-24mm) is perfect here.",
    "Bring a solid carbon tripod for low-light shots.",
    "Highly recommend an ND filter for long exposures.",
    "A fast f/1.8 prime lens works best after dusk.",
    "Circular polarizer will save you from water glare.",
]

COMP_POOL = [
    "Use the leading lines of the pathway towards the center.",
    "Get extremely low to frame elements in the foreground.",
    "Position your subject on the right third of the frame.",
    "Shoot through the tree branches for a natural vignette.",
    "Catch the light reflections on wet surfaces.",
]


def make_review(spot_id: str, spot_name: str, user_uid: str, created_at: datetime):
    review_id = str(uuid4())
    photo_count = random.randint(1, 3)
    photo_urls = [f"https://picsum.photos/seed/{review_id}-{i}/800/600" for i in range(photo_count)]
    times = random.sample(BEST_TIMES, k=random.randint(1, 2))
    return review_id, {
        "spot_id": spot_id,
        "spot_name": spot_name,
        "user_id": user_uid,
        "photo_urls": photo_urls,
        "overall_rating": random.choices([3, 4, 5], weights=[1, 3, 2])[0],
        "notes": random.choice(NOTES_POOL),
        "best_time_of_day": times,
        "access_level": random.choices(ACCESS_LEVELS, weights=[3, 2, 1])[0],
        "entrance_fee": random.choice(ENTRANCE_FEES),
        "crowd_level": random.choices(CROWD_LEVELS, weights=[1, 3, 3, 1])[0],
        "best_season": random.sample(SEASONS, k=random.randint(1, 2)),
        "permit_required": random.choice([True, False]),
        "drone_allowed": random.choice([True, False]),
        "tripod_allowed": random.choice([True, False]),
        "gear_recommendations": random.choice(GEAR_POOL),
        "composition_hints": random.choice(COMP_POOL),
        "created_at": created_at,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project", required=True, help="Firebase project ID (must start with 'scout-dev')"
    )
    parser.add_argument("--users", type=int, default=3)
    parser.add_argument("--spots", type=int, default=8)
    parser.add_argument("--min-reviews", type=int, default=2)
    parser.add_argument("--max-reviews", type=int, default=4)
    parser.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    parser.add_argument("--center-lng", type=float, default=DEFAULT_CENTER_LNG)
    parser.add_argument("--radius-km", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    using_service_account = bool(cred_path and os.path.exists(cred_path))
    auth_method = f"service account: {cred_path}" if using_service_account else "gcloud ADC"

    if not args.yes:
        print(f"[seed] About to write fake data to REAL Firestore project: {args.project}")
        print(f"       Auth: {auth_method}")
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            sys.exit("[seed] Aborted.")

    random.seed(args.seed)

    # ---- Init Admin SDK against the real project ----
    if using_service_account:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {"projectId": args.project})
    else:
        # Application Default Credentials from `gcloud auth application-default login`
        firebase_admin.initialize_app(options={"projectId": args.project})
    db = firestore.client()

    now = datetime.now(timezone.utc)

    # ---- 1. Create users via Admin SDK (no passwords, no tokens) ----
    user_names = ["Alice Chen", "Bob Rivera", "Carol Kim", "Dana Patel", "Evan Wu"]
    users = []
    for i in range(args.users):
        display = user_names[i] if i < len(user_names) else f"Test User {i + 1}"
        email = f"seed-{display.split()[0].lower()}@example.com"
        try:
            user_record = auth.create_user(email=email, display_name=display)
            uid = user_record.uid
        except auth.EmailAlreadyExistsError:
            user_record = auth.get_user_by_email(email)
            uid = user_record.uid
        users.append({"uid": uid, "email": email, "display_name": display})
    print(f"[seed] Created/found {len(users)} users in Firebase Auth.")

    # ---- 2. Write user docs (review_count filled in after reviews are generated) ----
    review_counts: dict[str, int] = {u["uid"]: 0 for u in users}

    # ---- 3. Generate spots and reviews ----
    spot_ids = []
    total_reviews = 0
    for i in range(args.spots):
        spot_id = str(uuid4())
        spot_ids.append(spot_id)
        lat, lng = jittered_coord(args.center_lat, args.center_lng, args.radius_km)
        name = SPOT_NAMES[i] if i < len(SPOT_NAMES) else f"Test Spot {i + 1}"

        spot_created = now - timedelta(days=random.randint(7, 90))
        spot_doc = {
            "name": name,
            "public_lat": lat,
            "public_lng": lng,
            "city": "Los Angeles",
            "admin_area": "California",
            "country": "United States",
            "created_at": spot_created,
            **empty_aggregates(),
        }

        num_reviews = random.randint(args.min_reviews, args.max_reviews)
        review_offsets = sorted(
            random.uniform(0.5, (now - spot_created).total_seconds() / 86400.0)
            for _ in range(num_reviews)
        )
        reviews = []
        for offset_days in review_offsets:
            created_at = spot_created + timedelta(days=offset_days)
            author = random.choice(users)
            review_id, review = make_review(spot_id, name, author["uid"], created_at)
            reviews.append((review_id, review))
            review_counts[author["uid"]] += 1
            spot_doc = update_or_init_aggregates(spot_doc, review, review_id)

        batch = db.batch()
        batch.set(db.collection("spots").document(spot_id), spot_doc)
        for rid, review in reviews:
            batch.set(db.collection("reviews").document(rid), review)
        batch.commit()
        total_reviews += len(reviews)

    # ---- 4. Write user docs now that review_count is known ----
    user_batch = db.batch()
    for u in users:
        user_batch.set(
            db.collection("users").document(u["uid"]),
            {
                "uid": u["uid"],
                "email": u["email"],
                "display_name": u["display_name"],
                "photo_url": None,
                "created_at": now,
                "review_count": review_counts[u["uid"]],
            },
        )
    user_batch.commit()

    print(f"[seed] Wrote {args.spots} spots, {total_reviews} reviews to {args.project}.")

    print("\n=== Seed summary ===")
    print(f"Project: {args.project}")
    print(f"Center: lat={args.center_lat} lng={args.center_lng} radius_km={args.radius_km}")
    print("\nUsers (created in Firebase Auth — sign in from iOS to get a real ID token):")
    for u in users:
        print(f"  - {u['email']}  uid={u['uid']}")
    print("\nSample spot IDs:")
    for sid in spot_ids[:3]:
        print(f"  - {sid}")


if __name__ == "__main__":
    main()
