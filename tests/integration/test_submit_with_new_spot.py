"""Integration tests for POST /spots/with-review — create spot + first review."""

import io

from PIL import Image


def _make_jpeg():
    """Create a valid JPEG file-like for upload."""
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("photo.jpg", buf, "image/jpeg")


def _spot_review_form_data(**overrides):
    """Default valid form fields for spot + review creation."""
    data = {
        "name": "New Test Spot",
        "lat": "34.0522",
        "lng": "-118.2437",
        "overall_rating": "5",
        "notes": "Amazing discovery!",
        "best_time_of_day": "Sunrise",
        "access_level": "Easy",
        "entrance_fee": "Free",
        "crowd_level": "Empty",
        "environment": "Urban",
        "permit_required": False,
        "drone_allowed": False,
        "tripod_allowed": True,
        "gear_recommendations": "Wide lens",
        "composition_hints": "Low angle",
    }
    data.update(overrides)
    return data


class TestSubmitWithNewSpot:
    """Test spot + review creation."""

    def test_happy_path(self, client, auth_headers):
        """Happy path → spot + review created, geocoding data populated."""
        r = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 201
        body = r.json()

        # Spot fields
        spot = body["spot"]
        assert spot["name"] == "New Test Spot"
        assert spot["public_lat"] == 34.0522
        assert spot["public_lng"] == -118.2437
        assert spot["city"] == "Los Angeles"  # from mock geocoding
        assert spot["admin_area"] == "California"
        assert spot["country"] == "United States"
        assert spot["review_count"] == 1
        assert spot["avg_rating"] == 5.0
        assert spot["mode_access_level"] == "Easy"
        assert len(spot["recent_review_photos"]) == 1

        # Review fields
        review = body["review"]
        assert review["spot_id"] == spot["id"]
        assert review["overall_rating"] == 5
        assert len(review["photo_urls"]) == 1

    def test_geocoding_failure_503(self, client, auth_headers):
        """Geocoding failure → 503, nothing in Firestore."""
        from app.services import geocoding

        async def failing_geocode(lat, lng):
            from app.core.exceptions import GeocodingFailed

            raise GeocodingFailed("HTTP 500")

        original = geocoding.reverse
        geocoding.reverse = failing_geocode

        try:
            r = client.post(
                "/spots/with-review",
                data=_spot_review_form_data(),
                files=[("photos", _make_jpeg())],
                headers=auth_headers,
            )
            assert r.status_code == 503
            assert r.json()["code"] == "GEOCODING_FAILED"
        finally:
            geocoding.reverse = original

    def test_bad_enum_rejected(self, client, auth_headers):
        """Invalid enum → 400 before any work is done."""
        r = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(environment="Forest"),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_ENUM_VALUE"

    def test_spot_queryable_after_creation(self, client, auth_headers):
        """Created spot is findable via nearby query."""
        # Create
        r = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 201
        spot_id = r.json()["spot"]["id"]

        # Query nearby
        r2 = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 1},
            headers=auth_headers,
        )
        assert r2.status_code == 200
        spot_ids = [s["id"] for s in r2.json()]
        assert spot_id in spot_ids

    def test_requires_auth(self, client):
        """Missing auth → 401."""
        r = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(),
            files=[("photos", _make_jpeg())],
        )
        assert r.status_code == 401
