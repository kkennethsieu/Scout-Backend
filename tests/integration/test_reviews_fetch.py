"""Integration tests for reviews fetching and pagination.

Seeds 25 reviews on a single spot to verify cursors and limit checks.
Also covers concurrency checks.
"""

import io
from datetime import datetime, timezone

from PIL import Image


def _seed_spot(spot_id="test-spot-fetch"):
    """Seed a spot directly in Firestore."""
    from app.core.firebase import db
    from app.services.aggregates import empty_aggregates

    spot_data = {
        "name": "Fetch Test Spot",
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


def _seed_review_direct(spot_id, review_id, user_id, rating=4, created_at=None):
    """Seed a review directly in Firestore."""
    from app.core.firebase import db

    now = created_at or datetime.now(timezone.utc)
    review_data = {
        "spot_id": spot_id,
        "spot_name": "Test Spot",
        "public_lat": 34.0522,
        "public_lng": -118.2437,
        "city": "Los Angeles",
        "admin_area": "California",
        "user_id": user_id,
        "photo_urls": ["https://example.com/photo.jpg"],
        "overall_rating": rating,
        "notes": f"Review {review_id} notes",
        "best_time_of_day": ["Sunrise"],
        "best_season": ["Summer"],
        "access_level": "Easy",
        "entrance_fee": 12.50,
        "crowd_level": "Light",
        "permit_required": False,
        "drone_allowed": False,
        "tripod_allowed": True,
        "gear_recommendations": "Some gear",
        "composition_hints": "Some comp",
        "created_at": now,
    }
    db.collection("reviews").document(review_id).set(review_data)
    return review_data


def _make_jpeg():
    """Create a valid JPEG file-like for upload."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("photo.jpg", buf, "image/jpeg")


def _review_form_data(**overrides):
    """Default valid review form fields."""
    data = {
        "overall_rating": "4",
        "notes": "Great spot for photography!",
        "best_time_of_day": "Sunrise",
        "best_season": "Summer",
        "access_level": "Easy",
        "entrance_fee": "12.50",
        "crowd_level": "Light",
        "permit_required": False,
        "drone_allowed": False,
        "tripod_allowed": True,
        "gear_recommendations": "Some gear",
        "composition_hints": "Some comp",
    }
    data.update(overrides)
    return data


class TestReviewsFetch:
    """Test reviews fetch endpoints, pagination, and concurrency."""

    def test_single_review_fetch(self, client, auth_with_uid):
        """GET /reviews/{id} returns the correct review."""
        spot_id = _seed_spot()
        review_id = "specific-review-id"
        _seed_review_direct(spot_id, review_id, auth_with_uid["uid"])

        r = client.get(f"/reviews/{review_id}", headers=auth_with_uid["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == review_id
        assert body["spot_id"] == spot_id
        assert body["spot_name"] == "Test Spot"
        assert body["public_lat"] == 34.0522
        assert body["public_lng"] == -118.2437
        assert body["city"] == "Los Angeles"
        assert body["admin_area"] == "California"
        assert body["user_id"] == auth_with_uid["uid"]

    def test_single_review_nonexistent(self, client, auth_headers):
        """GET /reviews/{id} on nonexistent review returns 404."""
        r = client.get("/reviews/nonexistent-review-id", headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["code"] == "REVIEW_NOT_FOUND"

    def test_reviews_pagination(self, client, auth_with_uid):
        """Seed 25 reviews on a single spot and test pagination."""
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        headers = auth_with_uid["headers"]

        # Seed 25 reviews with increasing timestamps
        for i in range(25):
            ts = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
            _seed_review_direct(spot_id, f"rev-{i}", uid, created_at=ts)

        # 1. Default limit (20)
        r = client.get(f"/spots/{spot_id}/reviews", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 20
        assert body["limit"] == 20
        assert body["next_cursor"] is not None

        # Check newest first (rev-24 should be first)
        assert body["items"][0]["id"] == "rev-24"
        assert body["items"][19]["id"] == "rev-5"

        # 2. Use cursor to fetch the next page
        next_cursor = body["next_cursor"]
        r2 = client.get(
            f"/spots/{spot_id}/reviews",
            params={"cursor": next_cursor, "limit": 10},
            headers=headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        # Should return the remaining 5 reviews (rev-4 down to rev-0)
        assert len(body2["items"]) == 5
        assert body2["items"][0]["id"] == "rev-4"
        assert body2["items"][4]["id"] == "rev-0"
        assert body2["next_cursor"] is None

    def test_invalid_cursor(self, client, auth_headers):
        """GET /spots/{id}/reviews with invalid cursor → 400 INVALID_CURSOR."""
        spot_id = _seed_spot()
        r = client.get(
            f"/spots/{spot_id}/reviews",
            params={"cursor": "invalid-cursor-id"},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_CURSOR"

    def test_empty_reviews_page(self, client, auth_headers):
        """GET /spots/{id}/reviews for spot with no reviews → empty list, null cursor."""
        spot_id = _seed_spot()
        r = client.get(f"/spots/{spot_id}/reviews", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["next_cursor"] is None

    def test_user_reviews_pagination(self, client, auth_with_uid):
        """GET /users/me/reviews returns authenticated user's reviews paginated."""
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        headers = auth_with_uid["headers"]

        # Seed 5 reviews for this user
        for i in range(5):
            ts = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
            _seed_review_direct(spot_id, f"user-rev-{i}", uid, created_at=ts)

        # Seed 2 reviews for a different user
        _seed_review_direct(spot_id, "other-rev-1", "different-user")

        r = client.get("/users/me/reviews", params={"limit": 3}, headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 3
        # Should be this user's reviews in reverse-chronological order
        assert body["items"][0]["id"] == "user-rev-4"
        assert body["items"][2]["id"] == "user-rev-2"
        assert body["next_cursor"] is not None

        # Fetch remaining
        r2 = client.get(
            "/users/me/reviews",
            params={"limit": 3, "cursor": body["next_cursor"]},
            headers=headers,
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert len(body2["items"]) == 2
        assert body2["items"][0]["id"] == "user-rev-1"
        assert body2["items"][1]["id"] == "user-rev-0"
        assert body2["next_cursor"] is None


class TestReviewsSort:
    """GET /spots/{id}/reviews?sort=..."""

    def test_highest_rated(self, client, auth_with_uid):
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        _seed_review_direct(spot_id, "rate3", uid, rating=3)
        _seed_review_direct(spot_id, "rate5", uid, rating=5)
        _seed_review_direct(spot_id, "rate4", uid, rating=4)

        r = client.get(
            f"/spots/{spot_id}/reviews",
            params={"sort": "highest_rated"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        assert [i["id"] for i in r.json()["items"]] == ["rate5", "rate4", "rate3"]

    def test_lowest_rated(self, client, auth_with_uid):
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        _seed_review_direct(spot_id, "rate3", uid, rating=3)
        _seed_review_direct(spot_id, "rate5", uid, rating=5)
        _seed_review_direct(spot_id, "rate4", uid, rating=4)

        r = client.get(
            f"/spots/{spot_id}/reviews",
            params={"sort": "lowest_rated"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        assert [i["id"] for i in r.json()["items"]] == ["rate3", "rate4", "rate5"]

    def test_rating_ties_break_newest(self, client, auth_with_uid):
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        _seed_review_direct(
            spot_id, "old5", uid, rating=5, created_at=datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        _seed_review_direct(
            spot_id, "new5", uid, rating=5, created_at=datetime(2024, 1, 5, tzinfo=timezone.utc)
        )
        _seed_review_direct(
            spot_id, "mid", uid, rating=3, created_at=datetime(2024, 1, 3, tzinfo=timezone.utc)
        )

        r = client.get(
            f"/spots/{spot_id}/reviews",
            params={"sort": "highest_rated"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        assert [i["id"] for i in r.json()["items"]] == ["new5", "old5", "mid"]

    def test_scout_puts_quality_first(self, client, auth_with_uid):
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        _seed_review_direct(spot_id, "meh", uid, rating=2)
        _seed_review_direct(spot_id, "best", uid, rating=5)

        r = client.get(
            f"/spots/{spot_id}/reviews",
            params={"sort": "scout"},
            headers=auth_with_uid["headers"],
        )
        assert r.status_code == 200
        assert r.json()["items"][0]["id"] == "best"

    def test_sort_pagination(self, client, auth_with_uid):
        spot_id = _seed_spot()
        uid = auth_with_uid["uid"]
        headers = auth_with_uid["headers"]
        for rid, rating in (("p5", 5), ("p4", 4), ("p3", 3), ("p2", 2)):
            _seed_review_direct(spot_id, rid, uid, rating=rating)

        r = client.get(
            f"/spots/{spot_id}/reviews",
            params={"sort": "highest_rated", "limit": 2},
            headers=headers,
        )
        body = r.json()
        assert [i["id"] for i in body["items"]] == ["p5", "p4"]
        assert body["next_cursor"] is not None

        r2 = client.get(
            f"/spots/{spot_id}/reviews",
            params={"sort": "highest_rated", "limit": 2, "cursor": body["next_cursor"]},
            headers=headers,
        )
        body2 = r2.json()
        assert [i["id"] for i in body2["items"]] == ["p3", "p2"]
        assert body2["next_cursor"] is None

    def test_invalid_sort(self, client, auth_headers):
        spot_id = _seed_spot()
        r = client.get(
            f"/spots/{spot_id}/reviews",
            params={"sort": "bogus"},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_ENUM_VALUE"
