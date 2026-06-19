"""Integration tests for searching a spot's reviews by review text.

Covers substring matching across notes / gear_recommendations / composition_hints,
case-insensitivity, pagination cursors, and auth.
"""

from datetime import datetime, timezone

from app.core.firebase import db
from app.services.aggregates import empty_aggregates


def _seed_spot(spot_id="search-spot"):
    """Seed a spot directly in Firestore."""
    spot_data = {
        "name": "Search Test Spot",
        "public_lat": 34.0522,
        "public_lng": -118.2437,
        "city": "Los Angeles",
        "admin_area": "California",
        "country": "United States",
        "created_at": datetime.now(timezone.utc),
        **empty_aggregates(),
    }
    db.collection("spots").document(spot_id).set(spot_data)
    return spot_id


def _seed_review_direct(spot_id, review_id, user_id, created_at=None, **fields):
    """Seed a review directly in Firestore. `fields` overrides text fields, etc."""
    now = created_at or datetime.now(timezone.utc)
    review_data = {
        "spot_id": spot_id,
        "spot_name": "Search Test Spot",
        "public_lat": 34.0522,
        "public_lng": -118.2437,
        "city": "Los Angeles",
        "admin_area": "California",
        "user_id": user_id,
        "photo_urls": ["https://example.com/photo.jpg"],
        "overall_rating": 4,
        "notes": None,
        "best_time_of_day": ["Sunrise"],
        "best_season": ["Summer"],
        "access_level": "Easy",
        "entrance_fee": 12.50,
        "crowd_level": "Light",
        "permit_required": False,
        "drone_allowed": False,
        "tripod_allowed": True,
        "gear_recommendations": None,
        "composition_hints": None,
        "created_at": now,
    }
    review_data.update(fields)
    db.collection("reviews").document(review_id).set(review_data)
    return review_data


class TestReviewsSearch:
    """GET /spots/{id}/reviews/search."""

    def test_matches_notes(self, client, auth_with_uid):
        """Query matches only the review whose notes contain it."""
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        _seed_review_direct(spot_id, "r-drone", uid, notes="Great drone shot here")
        _seed_review_direct(spot_id, "r-parking", uid, notes="Easy parking nearby")
        _seed_review_direct(spot_id, "r-sunset", uid, notes="Beautiful sunset colors")

        r = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "drone"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert [item["id"] for item in body["items"]] == ["r-drone"]
        assert body["next_cursor"] is None

    def test_matches_gear_and_composition(self, client, auth_with_uid):
        """Matches also hit gear_recommendations and composition_hints."""
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        _seed_review_direct(spot_id, "r-gear", uid, gear_recommendations="Bring a tripod")
        _seed_review_direct(spot_id, "r-comp", uid, composition_hints="Frame the archway")

        r1 = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "tripod"},
            headers=auth_with_uid["headers"],
        )
        assert [item["id"] for item in r1.json()["items"]] == ["r-gear"]

        r2 = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "archway"},
            headers=auth_with_uid["headers"],
        )
        assert [item["id"] for item in r2.json()["items"]] == ["r-comp"]

    def test_case_insensitive(self, client, auth_with_uid):
        """Query is case-insensitive."""
        spot_id = _seed_spot()
        _seed_review_direct(spot_id, "r-drone", auth_with_uid["uid"], notes="drone shot")

        r = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "DRONE"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        assert [item["id"] for item in r.json()["items"]] == ["r-drone"]

    def test_no_match(self, client, auth_with_uid):
        """No matching reviews → empty page, null cursor."""
        spot_id = _seed_spot()
        _seed_review_direct(spot_id, "r-1", auth_with_uid["uid"], notes="nothing relevant")

        r = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "waterfall"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["next_cursor"] is None

    def test_pagination_newest_first(self, client, auth_with_uid):
        """Matches paginate newest-first and the cursor walks the rest."""
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        headers = auth_with_uid["headers"]

        # 25 matching reviews with increasing timestamps + a few non-matches mixed in.
        for i in range(25):
            ts = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
            _seed_review_direct(spot_id, f"m-{i}", uid, created_at=ts, notes=f"drone run {i}")
        _seed_review_direct(spot_id, "skip-1", uid, notes="no keyword here")

        r = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "drone"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 20
        assert body["limit"] == 20
        assert body["items"][0]["id"] == "m-24"  # newest first
        assert body["items"][19]["id"] == "m-5"
        assert body["next_cursor"] is not None

        r2 = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "drone", "cursor": body["next_cursor"], "limit": 10},
            headers=headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert [item["id"] for item in body2["items"]] == [f"m-{i}" for i in range(4, -1, -1)]
        assert body2["next_cursor"] is None

    def test_invalid_cursor(self, client, auth_with_uid):
        """Unknown cursor → 400 INVALID_CURSOR."""
        spot_id = _seed_spot()
        _seed_review_direct(spot_id, "r-1", auth_with_uid["uid"], notes="drone shot")

        r = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "drone", "cursor": "not-a-real-id"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_CURSOR"

    def test_requires_auth(self, client):
        """Missing Authorization header → 401."""
        spot_id = _seed_spot()
        r = client.get(f"/spots/{spot_id}/reviews/search", params={"q": "drone"})
        assert r.status_code == 401

    def test_sort_reorders_matches(self, client, auth_with_uid):
        """`sort` reorders the matched set (highest_rated over matching reviews)."""
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        _seed_review_direct(spot_id, "lo", uid, notes="drone shot", overall_rating=2)
        _seed_review_direct(spot_id, "hi", uid, notes="drone pano", overall_rating=5)
        _seed_review_direct(spot_id, "mid", uid, notes="drone clip", overall_rating=3)

        r = client.get(
            f"/spots/{spot_id}/reviews/search",
            params={"q": "drone", "sort": "highest_rated"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        assert [i["id"] for i in r.json()["items"]] == ["hi", "mid", "lo"]
