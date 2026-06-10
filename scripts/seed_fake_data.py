"""Seed the Firebase Emulator Suite with high-fidelity, beautiful mockup-backing spots, reviews, and users.

Run AFTER `make emulators` is up in another terminal:

    python -m scripts.seed_fake_data

The script targets ONLY the local emulators — it refuses to run against real
Firestore by hard-coding the emulator env vars before importing anything that
touches Firebase.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

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

# 4 High-fidelity Scenic California Spots with curated, beautiful real Unsplash landscape image pools
HIGH_FIDELITY_SPOTS = [
    {
        "id": "spot-griffith-observatory",
        "name": "Griffith Observatory Overlook",
        "lat": 34.1184,
        "lng": -118.3004,
        "city": "Los Angeles",
        "admin_area": "California",
        "country": "United States",
        "reviews": [
            {
                "rating": 5,
                "notes": "Stunning golden hour light hitting the front facade. Extremely busy but totally worth the trip.",
                "best_time_of_day": ["GoldenHour", "BlueHour"],
                "access_level": "Easy",
                "entrance_fee": 0.0,
                "crowd_level": "Crowded",
                "best_season": ["YearRound"],
                "permit_required": False,
                "drone_allowed": False,
                "tripod_allowed": False,
                "gear_recommendations": "Wide-angle lens (14-24mm) to capture the entire facade. Sturdy tripod is banned inside but tolerated outside in some parking boundaries.",
                "composition_hints": "Shoot from the front lawn path leading up to the main dome to get symmetrical leading lines. Catch the Hollywood sign from the western terrace.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1518391846015-55a9cc003b25?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "rating": 4,
                "notes": "Beautiful views of the city basin! Parking is expensive ($10/hr) on the hill, but walking up from the Greek Theatre is free and beautiful.",
                "best_time_of_day": ["Night"],
                "access_level": "Easy",
                "entrance_fee": 0.0,
                "crowd_level": "Moderate",
                "best_season": ["YearRound"],
                "permit_required": False,
                "drone_allowed": False,
                "tripod_allowed": False,
                "gear_recommendations": "A fast prime lens like a 35mm or 50mm f/1.8 is perfect for night portraits with the city lights bokeh behind.",
                "composition_hints": "Position your subject on the western balcony to catch the sunset gradient and the lights of Hollywood starting to twinkle.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1542224566-6e85f2e6772f?auto=format&fit=crop&w=800&q=80"
                ],
            },
            {
                "rating": 5,
                "notes": "Caught a magical sunrise here! Barely anyone around compared to the chaotic evening crowd. The morning fog rolling over the valley is sublime.",
                "best_time_of_day": ["Sunrise"],
                "access_level": "Easy",
                "entrance_fee": 0.0,
                "crowd_level": "Light",
                "best_season": ["Winter"],
                "permit_required": False,
                "drone_allowed": False,
                "tripod_allowed": True,
                "gear_recommendations": "A telephoto lens (70-200mm) is excellent to isolate downtown LA skyscrapers cutting through the low morning fog.",
                "composition_hints": "Shoot from the south-east corner trail. Use the framing of the hillside pine branches to balance the LA skyline.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=800&q=80"
                ],
            },
        ],
    },
    {
        "id": "spot-santa-monica-pier",
        "name": "Santa Monica Pier Ferris Wheel",
        "lat": 34.0100,
        "lng": -118.4962,
        "city": "Santa Monica",
        "admin_area": "California",
        "country": "United States",
        "reviews": [
            {
                "rating": 5,
                "notes": "Outstanding ocean breeze and wonderful lighting at night. The neon lights of the ferris wheel reflecting on the wet sand is a photographer's dream.",
                "best_time_of_day": ["Night", "BlueHour"],
                "access_level": "Easy",
                "entrance_fee": 0.0,
                "crowd_level": "Crowded",
                "best_season": ["Summer"],
                "permit_required": False,
                "drone_allowed": False,
                "tripod_allowed": True,
                "gear_recommendations": "10-stop ND filter for long-exposure water smoothing during sunset. Bring a lens cloth to clean salt spray off your optics.",
                "composition_hints": "Walk down to the sand underneath the pier structure to frame the glowing ferris wheel through the giant wooden pilings.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1498654896293-37aacf113fd9?auto=format&fit=crop&w=800&q=80",
                    "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80",
                ],
            },
            {
                "rating": 4,
                "notes": "Classic beach spot! Very crowded during midday, but walking along the boardwalk around golden hour is incredible. Great street photography spot.",
                "best_time_of_day": ["GoldenHour"],
                "access_level": "Easy",
                "entrance_fee": 0.0,
                "crowd_level": "Crowded",
                "best_season": ["Summer", "Fall"],
                "permit_required": False,
                "drone_allowed": False,
                "tripod_allowed": True,
                "gear_recommendations": "A high-quality circular polarizer to cut glare off the ocean waves and saturate the deep sky blue.",
                "composition_hints": "Get a high-angle shot from the Palisade Bluffs overlooking the pier entrance and the coastal highway below.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1505118380757-91f5f5632de0?auto=format&fit=crop&w=800&q=80"
                ],
            },
        ],
    },
    {
        "id": "spot-yosemite-valley",
        "name": "Yosemite Valley Tunnel View",
        "lat": 37.7456,
        "lng": -119.5332,
        "city": "Yosemite Valley",
        "admin_area": "California",
        "country": "United States",
        "reviews": [
            {
                "rating": 5,
                "notes": "Breathtaking grandeur. Standing at the overlook and seeing El Capitan and Half Dome rise up is an unforgettable experience.",
                "best_time_of_day": ["Sunrise", "GoldenHour"],
                "access_level": "Moderate",
                "entrance_fee": 35.00,
                "crowd_level": "Moderate",
                "best_season": ["Spring", "Fall"],
                "permit_required": True,
                "drone_allowed": False,
                "tripod_allowed": True,
                "gear_recommendations": "Wide-angle zoom (16-35mm) to capture both granite faces. A sturdy carbon tripod is necessary to withstand valley winds.",
                "composition_hints": "The classic composition puts El Capitan on the left, Bridalveil Fall on the right, and Half Dome sitting majestically in the center.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1426604966848-d7adac402bff?auto=format&fit=crop&w=800&q=80"
                ],
            },
            {
                "rating": 5,
                "notes": "Did some afternoon hiking down in the valley meadows. The reflection of El Capitan in the Merced River is absolutely gorgeous.",
                "best_time_of_day": ["Midday"],
                "access_level": "Moderate",
                "entrance_fee": 35.00,
                "crowd_level": "Light",
                "best_season": ["Spring"],
                "permit_required": True,
                "drone_allowed": False,
                "tripod_allowed": True,
                "gear_recommendations": "Telephoto zoom (70-200mm) is excellent to isolate climbing teams on El Cap or detail the raging waterfalls.",
                "composition_hints": "Valley View parking pull-out captures the river in the foreground, acting as a perfect leading line towards the mountains.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=800&q=80"
                ],
            },
        ],
    },
    {
        "id": "spot-joshua-tree",
        "name": "Joshua Tree Arch Rock",
        "lat": 34.0128,
        "lng": -116.1681,
        "city": "Joshua Tree",
        "admin_area": "California",
        "country": "United States",
        "reviews": [
            {
                "rating": 5,
                "notes": "One of the best dark sky areas in California! The Milky Way is clearly visible to the naked eye. Unreal desert landscape.",
                "best_time_of_day": ["Night"],
                "access_level": "Difficult",
                "entrance_fee": 30.00,
                "crowd_level": "Light",
                "best_season": ["Spring", "Fall"],
                "permit_required": True,
                "drone_allowed": False,
                "tripod_allowed": True,
                "gear_recommendations": "A fast wide prime lens (20mm f/1.8 or 24mm f/1.4). Red headlamp to protect your night-vision adaptation.",
                "composition_hints": "Position your tripod low inside the rocky wash to frame the core of the Milky Way arching directly over the natural stone arch.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1532960401447-7dd05bef20b0?auto=format&fit=crop&w=800&q=80"
                ],
            },
            {
                "rating": 5,
                "notes": "Beautiful sunset over the desert rocks! The Joshua Trees form incredible silhouettes against the deep orange sky.",
                "best_time_of_day": ["GoldenHour"],
                "access_level": "Difficult",
                "entrance_fee": 30.00,
                "crowd_level": "Light",
                "best_season": ["Fall", "Winter"],
                "permit_required": True,
                "drone_allowed": False,
                "tripod_allowed": True,
                "gear_recommendations": "A graduated ND filter to handle the extreme dynamic range between the bright sky and dark desert foreground.",
                "composition_hints": "Isolate a single, particularly gnarly Joshua Tree as your primary foreground anchor, offset to the right third of the frame.",
                "photo_urls": [
                    "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=800&q=80"
                ],
            },
        ],
    },
]

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
    """Wipe the emulator's Firestore via its REST endpoint."""
    url = f"http://{FIRESTORE_HOST}/emulator/v1/projects/{PROJECT_ID}/databases/(default)/documents"
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


# --- Main ------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed high-fidelity fake data into the Firestore emulator."
    )
    parser.add_argument(
        "--no-clear",
        dest="clear",
        action="store_false",
        help="Don't wipe Firestore before seeding (default: wipe).",
    )
    parser.set_defaults(clear=True)
    args = parser.parse_args()

    check_emulators()

    # Import only after emulator env vars are set.
    from app.core.firebase import db, init_firebase
    from app.services.aggregates import empty_aggregates, update_or_init_aggregates

    init_firebase()

    if args.clear:
        clear_firestore()

    # 1. Mint users
    users: list[dict] = []
    user_configs = [
        ("seed-alice@example.com", "Alice Chen"),
        ("seed-bob@example.com", "Bob Rivera"),
        ("seed-carol@example.com", "Carol Kim"),
        ("seed-dana@example.com", "Dana Patel"),
    ]
    for email, display in user_configs:
        users.append(mint_user(email=email, display_name=display))
    print(f"[seed] Minted {len(users)} users via Auth Emulator.")

    now = datetime.now(timezone.utc)

    # 2. User docs are written after reviews so review_count is known.
    review_counts: dict[str, int] = {u["uid"]: 0 for u in users}

    # 3. For each high-fidelity spot: seed reviews, replay aggregates, batch write
    total_reviews = 0
    for spot_cfg in HIGH_FIDELITY_SPOTS:
        spot_id = spot_cfg["id"]
        spot_created = now - timedelta(days=60)
        spot_doc = {
            "name": spot_cfg["name"],
            "public_lat": spot_cfg["lat"],
            "public_lng": spot_cfg["lng"],
            "city": spot_cfg["city"],
            "admin_area": spot_cfg["admin_area"],
            "country": spot_cfg["country"],
            "created_at": spot_created,
            **empty_aggregates(),
        }

        reviews_to_write = []
        review_configs = spot_cfg["reviews"]

        # Date reviews sequentially to preserve clean chronological aggregations
        for index, r_cfg in enumerate(review_configs):
            review_id = f"rev-{spot_id}-{index}"
            author = users[index % len(users)]
            created_at = spot_created + timedelta(days=10 * (index + 1))

            review_doc = {
                "spot_id": spot_id,
                "spot_name": spot_cfg["name"],
                "public_lat": spot_cfg["lat"],
                "public_lng": spot_cfg["lng"],
                "city": spot_cfg["city"],
                "admin_area": spot_cfg["admin_area"],
                "user_id": author["uid"],
                "photo_urls": r_cfg["photo_urls"],
                "overall_rating": r_cfg["rating"],
                "notes": r_cfg["notes"],
                "best_time_of_day": r_cfg["best_time_of_day"],
                "access_level": r_cfg["access_level"],
                "entrance_fee": r_cfg["entrance_fee"],
                "crowd_level": r_cfg["crowd_level"],
                "best_season": r_cfg["best_season"],
                "permit_required": r_cfg["permit_required"],
                "drone_allowed": r_cfg["drone_allowed"],
                "tripod_allowed": r_cfg["tripod_allowed"],
                "gear_recommendations": r_cfg["gear_recommendations"],
                "composition_hints": r_cfg["composition_hints"],
                "created_at": created_at,
            }
            reviews_to_write.append((review_id, review_doc))
            review_counts[author["uid"]] += 1
            spot_doc = update_or_init_aggregates(spot_doc, review_doc, review_id)

        # Batch write spot and reviews
        batch = db.batch()
        batch.set(db.collection("spots").document(spot_id), spot_doc)
        for rid, r_doc in reviews_to_write:
            batch.set(db.collection("reviews").document(rid), r_doc)
        batch.commit()
        total_reviews += len(reviews_to_write)

    print(f"[seed] Wrote {len(HIGH_FIDELITY_SPOTS)} high-fidelity spots, {total_reviews} reviews.")

    # 4. Write user docs now that review_count is known
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

    # 5. Summary output
    print("\n=== Seed summary ===")
    print("Users (use one of these tokens as `Authorization: Bearer <idToken>`):")
    for u in users:
        print(f"  - {u['email']}  uid={u['uid']}")
        print(f"      idToken={u['id_token']}")
    print("\nHigh-Fidelity Spots Seeded:")
    for spot_cfg in HIGH_FIDELITY_SPOTS:
        print(f"  - {spot_cfg['name']} (ID: {spot_cfg['id']})")
        print(f"      Coords: ({spot_cfg['lat']}, {spot_cfg['lng']}) in {spot_cfg['city']}")
    print(
        "\nTry querying nearby Griffith Observatory:\n"
        "  curl -H 'Authorization: Bearer <idToken>' "
        "'http://localhost:8000/spots?lat=34.1184&lng=-118.3004&radius_km=10'"
    )


if __name__ == "__main__":
    main()
