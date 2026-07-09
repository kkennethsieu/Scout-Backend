"""Integration tests for PATCH /reviews/{id}.

Covers ownership enforcement, PATCH merge semantics (partial update, explicit
clear, empty no-op), spot aggregate re-derivation on a rating change, and the
updated_at marker.
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
        "notes": "original notes",
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


class TestEditReview:
    def test_edit_updates_content_and_sets_updated_at(self, client, auth_with_uid):
        """PATCH changes the sent fields and stamps updated_at; created_at is untouched."""
        headers = auth_with_uid["headers"]
        spot_id = _seed_spot()
        review = _submit(client, spot_id, headers)
        assert review["updated_at"] is None

        r = client.patch(
            f"/reviews/{review['id']}",
            json={"overall_rating": 2, "notes": "edited notes"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["overall_rating"] == 2
        assert body["notes"] == "edited notes"
        assert body["updated_at"] is not None
        assert body["created_at"] == review["created_at"]

        # Persisted
        fetched = client.get(f"/reviews/{review['id']}", headers=headers).json()
        assert fetched["overall_rating"] == 2
        assert fetched["notes"] == "edited notes"

    def test_partial_patch_leaves_other_fields_intact(self, client, auth_with_uid):
        """Omitted fields are untouched."""
        headers = auth_with_uid["headers"]
        spot_id = _seed_spot()
        review = _submit(client, spot_id, headers, overall_rating="5", notes="keep me")

        r = client.patch(
            f"/reviews/{review['id']}",
            json={"crowd_level": "Crowded"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["crowd_level"] == "Crowded"
        assert body["overall_rating"] == 5  # untouched
        assert body["notes"] == "keep me"  # untouched

    def test_explicit_null_clears_field(self, client, auth_with_uid):
        """Sending an explicit null clears a previously-set field."""
        headers = auth_with_uid["headers"]
        spot_id = _seed_spot()
        review = _submit(client, spot_id, headers, notes="delete me")

        r = client.patch(
            f"/reviews/{review['id']}",
            json={"notes": None},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["notes"] is None

    def test_edit_rating_recomputes_spot_aggregates(self, client, auth_headers_for):
        """Editing one review's rating re-derives the spot's avg_rating."""
        spot_id = _seed_spot()
        user_a = auth_headers_for(email="a@example.com")
        user_b = auth_headers_for(email="b@example.com")

        review_a = _submit(client, spot_id, user_a["headers"], overall_rating="5")
        _submit(client, spot_id, user_b["headers"], overall_rating="3")

        spot = client.get(f"/spots/{spot_id}", headers=user_a["headers"]).json()
        assert spot["avg_rating"] == 4.0

        # A drops their rating 5 → 1  →  avg becomes (1 + 3) / 2 = 2.0
        r = client.patch(
            f"/reviews/{review_a['id']}",
            json={"overall_rating": 1},
            headers=user_a["headers"],
        )
        assert r.status_code == 200, r.text

        spot = client.get(f"/spots/{spot_id}", headers=user_a["headers"]).json()
        assert spot["review_count"] == 2  # unchanged by an edit
        assert spot["avg_rating"] == 2.0

    def test_empty_patch_is_noop(self, client, auth_with_uid):
        """An empty body changes nothing and does not stamp updated_at."""
        headers = auth_with_uid["headers"]
        spot_id = _seed_spot()
        review = _submit(client, spot_id, headers)

        r = client.patch(f"/reviews/{review['id']}", json={}, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["updated_at"] is None

    def test_cannot_edit_another_users_review(self, client, auth_headers_for):
        """A non-author gets 403 and the review is unchanged."""
        spot_id = _seed_spot()
        owner = auth_headers_for(email="owner@example.com")
        other = auth_headers_for(email="other@example.com")
        review = _submit(client, spot_id, owner["headers"], overall_rating="5")

        r = client.patch(
            f"/reviews/{review['id']}",
            json={"overall_rating": 1},
            headers=other["headers"],
        )
        assert r.status_code == 403
        assert r.json()["code"] == "FORBIDDEN"
        # Unchanged
        assert (
            client.get(f"/reviews/{review['id']}", headers=owner["headers"]).json()[
                "overall_rating"
            ]
            == 5
        )

    def test_edit_nonexistent_review_404(self, client, auth_headers):
        r = client.patch(
            "/reviews/does-not-exist", json={"overall_rating": 3}, headers=auth_headers
        )
        assert r.status_code == 404
        assert r.json()["code"] == "REVIEW_NOT_FOUND"

    def test_edit_requires_auth(self, client):
        r = client.patch("/reviews/whatever", json={"overall_rating": 3})
        assert r.status_code == 401

    def test_invalid_rating_rejected(self, client, auth_with_uid):
        """Out-of-range rating is rejected by validation (400 via the handler)."""
        headers = auth_with_uid["headers"]
        spot_id = _seed_spot()
        review = _submit(client, spot_id, headers)

        r = client.patch(
            f"/reviews/{review['id']}",
            json={"overall_rating": 9},
            headers=headers,
        )
        assert r.status_code == 400
