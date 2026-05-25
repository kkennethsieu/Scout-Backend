"""Integration tests for GET /spots/{id} — single spot fetch."""

from datetime import datetime, timezone


def _seed_spot(spot_id, name="Test Spot"):
    """Seed a spot directly in Firestore emulator."""
    from app.core.firebase import db
    from app.services.aggregates import empty_aggregates

    spot_data = {
        "name": name,
        "public_lat": 34.0522,
        "public_lng": -118.2437,
        "city": "Los Angeles",
        "admin_area": "California",
        "country": "United States",
        "created_at": datetime.now(timezone.utc),
        **empty_aggregates(),
    }
    db.collection("spots").document(spot_id).set(spot_data)


class TestSpotsGet:
    """Test single spot fetch."""

    def test_get_existing_spot(self, client, auth_headers):
        """Existing spot → 200 with full data."""
        _seed_spot("spot-123", "Downtown View")
        r = client.get("/spots/spot-123", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "spot-123"
        assert body["name"] == "Downtown View"
        assert body["public_lat"] == 34.0522
        assert body["city"] == "Los Angeles"
        assert body["review_count"] == 0
        assert "recent_review_photos" in body

    def test_nonexistent_spot_404(self, client, auth_headers):
        """Nonexistent spot → 404 SPOT_NOT_FOUND."""
        r = client.get("/spots/does-not-exist", headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["code"] == "SPOT_NOT_FOUND"
