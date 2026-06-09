"""Integration tests for DELETE /reviews/{id}.

Covers ownership enforcement, user review_count increment/decrement, spot
aggregate reversal, and spot deletion when its last review is removed.
"""

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
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("photo.jpg", buf, "image/jpeg")


def _form(**overrides):
    data = {
        "overall_rating": "4",
        "access_level": "Easy",
        "entrance_fee": "12.50",
        "crowd_level": "Light",
    }
    data.update(overrides)
    return data


def _submit(client, spot_id, headers, **overrides):
    r = client.post(
        f"/spots/{spot_id}/reviews",
        data=_form(**overrides),
        files=[("photos", _make_jpeg())],
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestDeleteReview:
    def test_create_then_delete_updates_user_count(self, client, auth_with_uid):
        """Creating a review bumps review_count; deleting it brings it back down."""
        headers = auth_with_uid["headers"]
        spot_id = _seed_spot()

        review = _submit(client, spot_id, headers)
        assert client.get("/users/me", headers=headers).json()["review_count"] == 1

        d = client.delete(f"/reviews/{review['id']}", headers=headers)
        assert d.status_code == 204
        assert client.get("/users/me", headers=headers).json()["review_count"] == 0
        # Review is gone
        assert client.get(f"/reviews/{review['id']}", headers=headers).status_code == 404

    def test_delete_reverses_spot_aggregates(self, client, auth_headers_for):
        """Deleting one of two reviews recomputes the spot's aggregates."""
        spot_id = _seed_spot()
        user_a = auth_headers_for(email="a@example.com")
        user_b = auth_headers_for(email="b@example.com")

        _submit(client, spot_id, user_a["headers"], overall_rating="5", entrance_fee="10.00")
        review_b = _submit(
            client,
            spot_id,
            user_b["headers"],
            overall_rating="3",
            entrance_fee="20.00",
            access_level="Difficult",
        )

        spot = client.get(f"/spots/{spot_id}", headers=user_a["headers"]).json()
        assert spot["review_count"] == 2
        assert spot["avg_rating"] == 4.0
        assert spot["avg_entrance_fee"] == 15.0

        # Delete user B's review → aggregates reflect only user A
        d = client.delete(f"/reviews/{review_b['id']}", headers=user_b["headers"])
        assert d.status_code == 204

        spot = client.get(f"/spots/{spot_id}", headers=user_a["headers"]).json()
        assert spot["review_count"] == 1
        assert spot["avg_rating"] == 5.0
        assert spot["avg_entrance_fee"] == 10.0
        assert spot["mode_access_level"] == "Easy"  # only A's "Easy" remains

        # Counts are per-user
        assert client.get("/users/me", headers=user_a["headers"]).json()["review_count"] == 1
        assert client.get("/users/me", headers=user_b["headers"]).json()["review_count"] == 0

    def test_deleting_last_review_deletes_spot(self, client, auth_with_uid):
        """Removing a spot's only review deletes the now-empty spot."""
        headers = auth_with_uid["headers"]
        spot_id = _seed_spot()
        review = _submit(client, spot_id, headers)

        d = client.delete(f"/reviews/{review['id']}", headers=headers)
        assert d.status_code == 204
        assert client.get(f"/spots/{spot_id}", headers=headers).status_code == 404

    def test_cannot_delete_another_users_review(self, client, auth_headers_for):
        """A non-author gets 403 and the review survives."""
        spot_id = _seed_spot()
        owner = auth_headers_for(email="owner@example.com")
        other = auth_headers_for(email="other@example.com")

        review = _submit(client, spot_id, owner["headers"])

        d = client.delete(f"/reviews/{review['id']}", headers=other["headers"])
        assert d.status_code == 403
        assert d.json()["code"] == "FORBIDDEN"
        # Review still there
        assert client.get(f"/reviews/{review['id']}", headers=owner["headers"]).status_code == 200

    def test_delete_nonexistent_review_404(self, client, auth_headers):
        r = client.delete("/reviews/does-not-exist", headers=auth_headers)
        assert r.status_code == 404
        assert r.json()["code"] == "REVIEW_NOT_FOUND"

    def test_delete_requires_auth(self, client):
        r = client.delete("/reviews/whatever")
        assert r.status_code == 401
