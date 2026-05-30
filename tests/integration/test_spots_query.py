"""Integration tests for GET /spots — nearby query.

Seeds spots in Firestore emulator, tests distance filtering and sorting.
"""

from datetime import datetime, timezone


def _seed_spot(client, spot_id, name, lat, lng):
    """Seed a spot directly in Firestore emulator."""
    from app.core.firebase import db
    from app.services.aggregates import empty_aggregates

    spot_data = {
        "name": name,
        "public_lat": lat,
        "public_lng": lng,
        "city": "Los Angeles",
        "admin_area": "California",
        "country": "United States",
        "created_at": datetime.now(timezone.utc),
        **empty_aggregates(),
    }
    db.collection("spots").document(spot_id).set(spot_data)


class TestSpotsQuery:
    """Test nearby spots query."""

    def test_empty_area(self, client, auth_headers):
        """No spots in area → empty list."""
        r = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_finds_nearby_spots(self, client, auth_headers):
        """Spots within radius are returned."""
        # Seed spots near downtown LA
        _seed_spot(client, "spot-1", "DTLA Spot", 34.0522, -118.2437)
        _seed_spot(client, "spot-2", "Hollywood Spot", 34.0928, -118.3287)
        _seed_spot(client, "spot-3", "Venice Spot", 33.9850, -118.4695)

        r = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 20},
            headers=auth_headers,
        )
        assert r.status_code == 200
        spots = r.json()
        assert len(spots) >= 2  # DTLA and Hollywood should be within 20km

    def test_distance_sorted(self, client, auth_headers):
        """Results are sorted by distance from query point."""
        _seed_spot(client, "spot-far", "Far Spot", 34.2, -118.0)
        _seed_spot(client, "spot-near", "Near Spot", 34.053, -118.244)
        _seed_spot(client, "spot-mid", "Mid Spot", 34.1, -118.1)

        r = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 50},
            headers=auth_headers,
        )
        assert r.status_code == 200
        spots = r.json()
        assert len(spots) == 3
        # First spot should be the nearest
        assert spots[0]["name"] == "Near Spot"

    def test_outside_radius_excluded(self, client, auth_headers):
        """Spots outside the radius are excluded."""
        _seed_spot(client, "spot-la", "LA Spot", 34.0522, -118.2437)
        _seed_spot(client, "spot-sf", "SF Spot", 37.7749, -122.4194)  # ~559km away

        r = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        spots = r.json()
        assert len(spots) == 1
        assert spots[0]["name"] == "LA Spot"

    def test_limit_respected(self, client, auth_headers):
        """Limit parameter caps results."""
        for i in range(5):
            _seed_spot(
                client,
                f"spot-{i}",
                f"Spot {i}",
                34.05 + i * 0.001,
                -118.24,
            )

        r = client.get(
            "/spots",
            params={"lat": 34.05, "lng": -118.24, "radius_km": 10, "limit": 2},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_lightweight_schema(self, client, auth_headers):
        """Verify nearby query returns lightweight SpotSummaryResponse without full aggregates."""
        _seed_spot(client, "spot-lightweight", "Lightweight Spot", 34.0522, -118.2437)

        r = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 5},
            headers=auth_headers,
        )
        assert r.status_code == 200
        spots = r.json()
        assert len(spots) == 1
        spot = spots[0]

        # Verify essential fields exist
        assert "id" in spot
        assert "name" in spot
        assert "public_lat" in spot
        assert "public_lng" in spot
        assert "city" in spot
        assert "review_count" in spot
        assert "avg_rating" in spot
        assert "cover_photo_url" in spot
        assert "recent_review_photos" in spot

        # Verify detailed fields are excluded
        assert "mode_access_level" not in spot
        assert "mode_entrance_fee" not in spot
        assert "mode_crowd_level" not in spot
        assert "mode_environment" not in spot
