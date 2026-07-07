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
        body = r.json()
        assert body["items"] == []
        assert body["next_cursor"] is None

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
        spots = r.json()["items"]
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
        spots = r.json()["items"]
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
        spots = r.json()["items"]
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
        assert len(r.json()["items"]) == 2

    def test_lightweight_schema(self, client, auth_headers):
        """Verify nearby query returns lightweight SpotSummaryResponse without full aggregates."""
        _seed_spot(client, "spot-lightweight", "Lightweight Spot", 34.0522, -118.2437)

        r = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 5},
            headers=auth_headers,
        )
        assert r.status_code == 200
        spots = r.json()["items"]
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
        assert "avg_entrance_fee" not in spot
        assert "mode_crowd_level" not in spot

    def test_cursor_pagination(self, client, auth_headers):
        """Paging with a cursor walks the full result set with no gaps or overlap."""
        for i in range(5):
            _seed_spot(client, f"page-spot-{i}", f"Spot {i}", 34.05 + i * 0.001, -118.24)

        seen = []
        cursor = None
        pages = 0
        while True:
            params = {"lat": 34.05, "lng": -118.24, "radius_km": 10, "limit": 2}
            if cursor:
                params["cursor"] = cursor
            r = client.get("/spots", params=params, headers=auth_headers)
            assert r.status_code == 200
            body = r.json()
            seen.extend(s["id"] for s in body["items"])
            cursor = body["next_cursor"]
            pages += 1
            if cursor is None:
                break
            assert pages < 10  # guard against an infinite loop

        # 5 spots over limit=2 → pages of 2, 2, 1; every spot seen exactly once.
        assert pages == 3
        assert len(seen) == 5
        assert len(set(seen)) == 5

    def test_invalid_cursor_rejected(self, client, auth_headers):
        """A malformed cursor → 400 INVALID_CURSOR."""
        r = client.get(
            "/spots",
            params={"lat": 34.05, "lng": -118.24, "radius_km": 10, "cursor": "!!notbase64!!"},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert r.json()["code"] == "INVALID_CURSOR"


class TestNearbyFallback:
    """GET /spots empty-result fallback to the predefined flagship location."""

    def test_fallback_when_empty(self, client, auth_headers):
        """No spots near the caller → returns flagship spots flagged is_fallback."""
        from app.core.config import settings

        # A spot at the configured fallback center (SF by default).
        _seed_spot(
            client, "flagship", "Flagship Spot", settings.FALLBACK_LAT, settings.FALLBACK_LNG
        )

        # Query a remote point with nothing nearby (Gulf of Guinea).
        r = client.get(
            "/spots",
            params={"lat": 0.0, "lng": 0.0, "radius_km": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["is_fallback"] is True
        assert body["next_cursor"] is None
        assert [s["name"] for s in body["items"]] == ["Flagship Spot"]

    def test_no_fallback_when_results_exist(self, client, auth_headers):
        """Real nearby spots are returned as-is, never flagged as fallback."""
        _seed_spot(client, "dtla", "DTLA Spot", 34.0522, -118.2437)

        r = client.get(
            "/spots",
            params={"lat": 34.0522, "lng": -118.2437, "radius_km": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["is_fallback"] is False
        assert len(body["items"]) == 1

    def test_no_fallback_on_pagination_tail(self, client, auth_headers):
        """An empty page reached via a cursor is end-of-results, not a fallback."""
        from app.services.spot_service import _encode_cursor

        # Flagship spot exists, but a cursor is present → paging, so no fallback.
        _seed_spot(client, "flagship", "Flagship Spot", 34.0522, -118.2437)
        cursor = _encode_cursor(1.0, "anything")

        r = client.get(
            "/spots",
            params={"lat": 0.0, "lng": 0.0, "radius_km": 10, "cursor": cursor},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["is_fallback"] is False
        assert body["items"] == []

    def test_fallback_disabled(self, client, auth_headers, monkeypatch):
        """With the kill-switch off, an empty region returns an empty list."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "NEARBY_FALLBACK_ENABLED", False)
        _seed_spot(
            client, "flagship", "Flagship Spot", settings.FALLBACK_LAT, settings.FALLBACK_LNG
        )

        r = client.get(
            "/spots",
            params={"lat": 0.0, "lng": 0.0, "radius_km": 10},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["is_fallback"] is False
        assert body["items"] == []
