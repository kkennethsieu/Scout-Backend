"""Seed the Firebase Emulator Suite with fake users, spots, and reviews.

Run AFTER `make emulators` is up in another terminal:

    python -m scripts.seed_fake_data

Or with flags:

    python -m scripts.seed_fake_data --users 3 --spots 10 --no-clear

The script targets ONLY the local emulators — it refuses to run against real
Firestore by hard-coding the emulator env vars before importing anything that
touches Firebase.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import requests

# --- Pin to the emulators BEFORE importing anything that touches Firebase. ---
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "127.0.0.1:9099"
os.environ["STORAGE_EMULATOR_HOST"] = "http://127.0.0.1:9199"
os.environ["GOOGLE_CLOUD_PROJECT"] = "scout-test"
os.environ.setdefault("STORAGE_BUCKET", "scout-test.appspot.com")
os.environ.setdefault("GEOCODING_API_KEY", "seed-unused")
os.environ["ENV"] = "test"

PROJECT_ID = "scout-test"
FIRESTORE_HOST = "127.0.0.1:8080"
AUTH_HOST = "http://127.0.0.1:9099"

# LA city hall — same coord the test fixtures use for the geocoding mock.
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
ENTRANCE_FEES = ["Free", "Paid", "Permit"]
CROWD_LEVELS = ["Empty", "Light", "Moderate", "Crowded"]
ENVIRONMENTS = ["Urban", "Nature", "Coastal", "Mountain", "Desert", "Indoor"]


# --- Emulator preflight ----------------------------------------------------


def check_emulators() -> None:
    """Bail out with a clear message if the emulators aren't reachable."""
    checks = [
        ("Firestore", f"http://{FIRESTORE_HOST}/"),
        ("Auth", f"{AUTH_HOST}/"),
    ]
    for name, url in checks:
        try:
            requests.get(url, timeout=1)
        except requests.RequestException:
            sys.exit(
                f"[seed] {name} emulator not reachable at {url}.\n"
                f"       Run `make emulators` in another terminal first."
            )


def clear_firestore() -> None:
    """Wipe the emulator's Firestore via its REST endpoint (same trick conftest uses)."""
    url = (
        f"http://{FIRESTORE_HOST}/emulator/v1/projects/{PROJECT_ID}"
        "/databases/(default)/documents"
    )
    requests.delete(url, timeout=5).raise_for_status()
    print("[seed] Cleared Firestore emulator.")


# --- Auth Emulator: mint users --------------------------------------------


def mint_user(email: str, display_name: str) -> dict:
    """Create-or-reuse an emulator user, then sign in to get an ID token."""
    password = "test-password-123"

    requests.post(
        f"{AUTH_HOST}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        json={
            "email": email,
            "password": password,
            "displayName": display_name,
            "returnSecureToken": True,
        },
        timeout=5,
    )

    r = requests.post(
        f"{AUTH_HOST}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key",
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=5,
    )
    r.raise_for_status()
    data = r.json()
    return {
        "uid": data["localId"],
        "email": email,
        "display_name": display_name,
        "id_token": data["idToken"],
    }


# --- Fake data generators --------------------------------------------------


def jittered_coord(center_lat: float, center_lng: float, max_km: float) -> tuple[float, float]:
    """Random point within roughly max_km of the center. Good enough for seeding."""
    # 1 degree latitude ≈ 111 km; longitude scales by cos(lat).
    import math

    dlat_km = random.uniform(-max_km, max_km)
    dlng_km = random.uniform(-max_km, max_km)
    dlat = dlat_km / 111.0
    dlng = dlng_km / (111.0 * math.cos(math.radians(center_lat)))
    return center_lat + dlat, center_lng + dlng


def make_review(spot_id: str, user_uid: str, created_at: datetime) -> tuple[str, dict]:
    review_id = str(uuid4())
    photo_count = random.randint(1, 3)
    photo_urls = [
        f"https://picsum.photos/seed/{review_id}-{i}/800/600" for i in range(photo_count)
    ]
    times = random.sample(BEST_TIMES, k=random.randint(1, 2))
    return review_id, {
        "spot_id": spot_id,
        "user_id": user_uid,
        "photo_urls": photo_urls,
        "overall_rating": random.choices([3, 4, 5], weights=[1, 3, 2])[0],
        "notes": random.choice(NOTES_POOL),
        "best_time_of_day": times,
        "access_level": random.choices(ACCESS_LEVELS, weights=[3, 2, 1])[0],
        "entrance_fee": random.choices(ENTRANCE_FEES, weights=[4, 1, 1])[0],
        "crowd_level": random.choices(CROWD_LEVELS, weights=[1, 3, 3, 1])[0],
        "environment": random.choice(ENVIRONMENTS),
        "created_at": created_at,
    }


# --- Main ------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed fake data into the Firestore emulator.")
    parser.add_argument("--users", type=int, default=3)
    parser.add_argument("--spots", type=int, default=10)
    parser.add_argument("--min-reviews", type=int, default=2)
    parser.add_argument("--max-reviews", type=int, default=4)
    parser.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    parser.add_argument("--center-lng", type=float, default=DEFAULT_CENTER_LNG)
    parser.add_argument("--radius-km", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility.")
    parser.add_argument(
        "--no-clear",
        dest="clear",
        action="store_false",
        help="Don't wipe Firestore before seeding (default: wipe).",
    )
    parser.set_defaults(clear=True)
    args = parser.parse_args()

    random.seed(args.seed)

    check_emulators()

    # Import only after emulator env vars are set.
    from app.core.firebase import db, init_firebase
    from app.services.aggregates import empty_aggregates, update_or_init_aggregates

    init_firebase()

    if args.clear:
        clear_firestore()

    # 1. Mint users.
    users: list[dict] = []
    user_names = ["Alice Chen", "Bob Rivera", "Carol Kim", "Dana Patel", "Evan Wu"]
    for i in range(args.users):
        display = user_names[i] if i < len(user_names) else f"Test User {i + 1}"
        email = f"seed-{display.split()[0].lower()}@example.com"
        users.append(mint_user(email=email, display_name=display))
    print(f"[seed] Minted {len(users)} users via Auth Emulator.")

    now = datetime.now(timezone.utc)

    # 2. Write user docs (matches the shape user_service.get_or_create_user produces).
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
            },
        )
    user_batch.commit()

    # 3. For each spot: generate reviews, replay aggregates, batch write.
    spot_ids: list[str] = []
    total_reviews = 0
    for i in range(args.spots):
        spot_id = str(uuid4())
        spot_ids.append(spot_id)
        lat, lng = jittered_coord(args.center_lat, args.center_lng, args.radius_km)
        name = (
            SPOT_NAMES[i] if i < len(SPOT_NAMES) else f"Test Spot {i + 1}"
        )

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
        # Reviews dated AFTER the spot, oldest first — replay order matters
        # so recent_review_photos ends up with newest at index 0.
        review_offsets = sorted(
            random.uniform(0.5, (now - spot_created).total_seconds() / 86400.0)
            for _ in range(num_reviews)
        )
        reviews: list[tuple[str, dict]] = []
        for offset_days in review_offsets:
            created_at = spot_created + timedelta(days=offset_days)
            author = random.choice(users)
            review_id, review = make_review(spot_id, author["uid"], created_at)
            reviews.append((review_id, review))
            spot_doc = update_or_init_aggregates(spot_doc, review, review_id)

        batch = db.batch()
        batch.set(db.collection("spots").document(spot_id), spot_doc)
        for rid, review in reviews:
            batch.set(db.collection("reviews").document(rid), review)
        batch.commit()
        total_reviews += len(reviews)

    print(f"[seed] Wrote {args.spots} spots, {total_reviews} reviews.")

    # 4. Summary.
    print("\n=== Seed summary ===")
    print(f"Center: lat={args.center_lat} lng={args.center_lng} radius_km={args.radius_km}")
    print("\nUsers (use one of these tokens as `Authorization: Bearer <idToken>`):")
    for u in users:
        print(f"  - {u['email']}  uid={u['uid']}")
        print(f"      idToken={u['id_token']}")
    print("\nSample spot IDs:")
    for sid in spot_ids[:3]:
        print(f"  - {sid}")
    print(
        f"\nTry:\n"
        f"  curl -H 'Authorization: Bearer <idToken>' "
        f"'http://localhost:8000/spots?lat={args.center_lat}&lng={args.center_lng}&radius_km={args.radius_km}'"
    )


if __name__ == "__main__":
    main()
