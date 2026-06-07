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
        "best_season": "Summer",
        "access_level": "Easy",
        "entrance_fee": "12.50",
        "crowd_level": "Empty",
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
        assert spot["avg_entrance_fee"] == 12.5  # "12.50" → 12.5, averaged over 1 review
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
            data=_spot_review_form_data(access_level="Sideways"),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_ENUM_VALUE"

    def test_bad_season_rejected(self, client, auth_headers):
        """Invalid best_season value → 400."""
        r = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(best_season="Autumn"),  # not in vocab (use Fall)
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

    def test_duplicate_spot_rejected_409(self, client, auth_headers):
        """Spot submitted within 50 meters of an existing spot is rejected with 409 Conflict."""
        # 1. Create first spot
        r1 = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(name="First Spot", lat="34.052200", lng="-118.243700"),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r1.status_code == 201
        first_spot_id = r1.json()["spot"]["id"]

        # 2. Try to submit second spot very close (e.g. lat offset of 0.0001 degrees, approx 11m away)
        r2 = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(
                name="Duplicate Close Spot", lat="34.052300", lng="-118.243700"
            ),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r2.status_code == 409
        body = r2.json()
        assert body["code"] == "SPOT_ALREADY_EXISTS"
        assert body["spot_id"] == first_spot_id
        assert body["name"] == "First Spot"
        assert 0.0 < body["distance_m"] < 20.0

        # 3. Submit a third spot further away (e.g. lat offset of 0.005 degrees, approx 550m away)
        r3 = client.post(
            "/spots/with-review",
            data=_spot_review_form_data(
                name="Distinct Far Spot", lat="34.057200", lng="-118.243700"
            ),
            files=[("photos", _make_jpeg())],
            headers=auth_headers,
        )
        assert r3.status_code == 201
        assert r3.json()["spot"]["name"] == "Distinct Far Spot"
