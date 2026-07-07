"""Integration tests for GET /spots/search — spot name search.

Seeds spots in the Firestore emulator and tests case-insensitive substring
matching, ranking, and limits.
"""

from datetime import datetime, timezone


def _seed_spot(spot_id, name, review_count=0):
    """Seed a spot directly in the Firestore emulator. Location is irrelevant
    to name search, so all spots share one coordinate."""
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
    spot_data["review_count"] = review_count
    db.collection("spots").document(spot_id).set(spot_data)


class TestSpotsSearch:
    def test_substring_match(self, client, auth_headers):
        """'fall' matches every spot containing it, and excludes the rest."""
        _seed_spot("s-horsetail", "Horsetail Fall")
        _seed_spot("s-yosemite", "Yosemite Falls")
        _seed_spot("s-bridalveil", "Bridalveil Fall")
        _seed_spot("s-dtla", "DTLA Rooftop")

        r = client.get("/spots/search", params={"q": "fall"}, headers=auth_headers)
        assert r.status_code == 200
        names = {s["name"] for s in r.json()}
        assert names == {"Horsetail Fall", "Yosemite Falls", "Bridalveil Fall"}

    def test_case_insensitive(self, client, auth_headers):
        """Query casing doesn't matter."""
        _seed_spot("s-horsetail", "Horsetail Fall")

        r = client.get("/spots/search", params={"q": "HORSETAIL"}, headers=auth_headers)
        assert r.status_code == 200
        assert [s["name"] for s in r.json()] == ["Horsetail Fall"]

    def test_ranking_exact_before_substring(self, client, auth_headers):
        """An exact name match ranks above a spot that merely contains the query."""
        _seed_spot("s-contains", "Lower Yosemite Fall Trail")
        _seed_spot("s-exact", "Yosemite")

        r = client.get("/spots/search", params={"q": "yosemite"}, headers=auth_headers)
        assert r.status_code == 200
        names = [s["name"] for s in r.json()]
        assert names[0] == "Yosemite"  # exact wins over substring

    def test_ranking_tiebreak_by_review_count(self, client, auth_headers):
        """Same match tier → more-reviewed spot ranks first."""
        _seed_spot("s-quiet", "Sunset Point", review_count=1)
        _seed_spot("s-popular", "Sunset Ridge", review_count=9)

        r = client.get("/spots/search", params={"q": "sunset"}, headers=auth_headers)
        assert r.status_code == 200
        assert [s["name"] for s in r.json()] == ["Sunset Ridge", "Sunset Point"]

    def test_limit_respected(self, client, auth_headers):
        """limit caps the number of results."""
        for i in range(5):
            _seed_spot(f"s-{i}", f"Beach Spot {i}")

        r = client.get("/spots/search", params={"q": "beach", "limit": 2}, headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_no_matches(self, client, auth_headers):
        """A query that matches nothing → empty list."""
        _seed_spot("s-horsetail", "Horsetail Fall")

        r = client.get("/spots/search", params={"q": "zzzznope"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_blank_query_rejected(self, client, auth_headers):
        """An empty q fails FastAPI validation (min_length=1) → 400."""
        r = client.get("/spots/search", params={"q": ""}, headers=auth_headers)
        assert r.status_code == 400

    def test_public_no_auth(self, client):
        """Public: no token → 200 (JWT not required)."""
        r = client.get("/spots/search", params={"q": "fall"})
        assert r.status_code == 200
