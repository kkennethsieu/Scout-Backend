"""Integration tests for POST /spots/{spot_id}/reviews — submit review for existing spot."""

import io
from datetime import datetime, timezone

from PIL import Image

from app.services.aggregates import empty_aggregates


def _seed_spot(spot_id="test-spot"):
    """Seed a spot directly in Firestore."""
    from app.core.firebase import db

    spot_data = {
        "name": "Test Spot",
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


def _make_jpeg():
    """Create a valid JPEG file-like for upload."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("photo.jpg", buf, "image/jpeg")


def _make_png():
    """Create a PNG file-like for upload."""
    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ("photo.png", buf, "image/png")


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
        "gear_recommendations": "Wide lens",
        "composition_hints": "Low angle",
    }
    data.update(overrides)
    return data


class TestSubmitExistingSpot:
    """Test review submission for existing spots."""

    def test_happy_path(self, client, auth_headers):
        """Happy path → review created, aggregates updated."""
        spot_id = _seed_spot()

        r = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["spot_id"] == spot_id
        assert body["spot_name"] == "Test Spot"
        assert body["overall_rating"] == 4
        assert body["access_level"] == "Easy"
        assert len(body["photo_urls"]) == 1
        assert body["photo_urls"][0].startswith("https://")

        # Verify aggregates updated on spot
        spot_r = client.get(f"/spots/{spot_id}", headers=auth_headers)
        spot = spot_r.json()
        assert spot["review_count"] == 1
        assert spot["avg_rating"] == 4.0
        assert spot["mode_access_level"] == "Easy"
        assert spot["avg_entrance_fee"] == 12.5
        assert len(spot["recent_review_photos"]) == 1

    def test_nonexistent_spot_404(self, client, auth_headers):
        """Nonexistent spot → 404 SPOT_NOT_FOUND."""
        r = client.post(
            "/spots/does-not-exist/reviews",
            data=_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 404
        assert r.json()["code"] == "SPOT_NOT_FOUND"

    def test_too_many_photos(self, client, auth_headers):
        """11 photos → 400 PHOTO_COUNT_INVALID (cap is 10)."""
        spot_id = _seed_spot()
        photos = [("photos", _make_jpeg()) for _ in range(11)]

        r = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=photos,
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "PHOTO_COUNT_INVALID"

    def test_zero_photos(self, client, auth_headers):
        """0 photos → 400 (FastAPI validation or our check)."""
        spot_id = _seed_spot()

        r = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=[],
            headers=auth_headers,
        )
        # Either 400 from our validation or 422 from FastAPI
        assert r.status_code in (400, 422)

    def test_bad_enum_value(self, client, auth_headers):
        """Bad enum value → 400 INVALID_ENUM_VALUE."""
        spot_id = _seed_spot()

        r = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(access_level="SuperEasy"),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_ENUM_VALUE"

    def test_png_photo_rejected(self, client, auth_headers):
        """PNG photo → 400 PHOTO_INVALID_FORMAT."""
        spot_id = _seed_spot()

        r = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=[("photos", _make_png())],
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "PHOTO_INVALID_FORMAT"

    def test_multiple_photos(self, client, auth_headers):
        """Multiple valid photos → all uploaded."""
        spot_id = _seed_spot()
        photos = [("photos", _make_jpeg()) for _ in range(3)]

        r = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=photos,
            headers=auth_headers,
        )
        assert r.status_code == 201
        assert len(r.json()["photo_urls"]) == 3

    def test_duplicate_review_same_user_409(self, client, auth_headers):
        """A user who already reviewed a spot → 409 REVIEW_ALREADY_EXISTS."""
        spot_id = _seed_spot()

        first = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert first.status_code == 201
        first_review_id = first.json()["id"]

        second = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert second.status_code == 409
        body = second.json()
        assert body["code"] == "REVIEW_ALREADY_EXISTS"
        assert body["spot_id"] == spot_id
        assert body["review_id"] == first_review_id

        # Aggregates unchanged — still a single review
        spot = client.get(f"/spots/{spot_id}", headers=auth_headers).json()
        assert spot["review_count"] == 1

    def test_different_user_can_review_same_spot(self, client, auth_headers_for):
        """A second, distinct user may review a spot the first already reviewed."""
        spot_id = _seed_spot()
        user_a = auth_headers_for(email="user_a@example.com")
        user_b = auth_headers_for(email="user_b@example.com")

        r1 = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=user_a["headers"],
        )
        assert r1.status_code == 201

        r2 = client.post(
            f"/spots/{spot_id}/reviews",
            data=_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=user_b["headers"],
        )
        assert r2.status_code == 201

        spot = client.get(f"/spots/{spot_id}", headers=user_a["headers"]).json()
        assert spot["review_count"] == 2

    def test_multiple_best_time_of_day(self, client, auth_headers):
        """Multiple best_time_of_day values (repeated key)."""
        spot_id = _seed_spot()

        # FastAPI TestClient handles repeated form fields via list
        data = _review_form_data()
        data["best_time_of_day"] = ["Sunrise", "GoldenHour"]

        r = client.post(
            f"/spots/{spot_id}/reviews",
            data=data,
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 201
        assert set(r.json()["best_time_of_day"]) == {"Sunrise", "GoldenHour"}
