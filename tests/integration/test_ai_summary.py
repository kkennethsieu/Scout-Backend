"""Integration tests for AI review summaries.

Requires the Firestore/Storage emulators (run via `make test`). Gemini is never
called: tests leave GEMINI_API_KEY empty, so maybe_regenerate_summary no-ops on
the missing key — these tests cover the surrounding plumbing (schema exposure and
summary preservation across the delete-review aggregate rebuild), not generation.
"""

import io
from datetime import datetime, timezone

from PIL import Image

from app.services.aggregates import empty_aggregates


def _seed_spot(spot_id="ai-spot", **extra):
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
        **extra,
    }
    db.collection("spots").document(spot_id).set(spot_data)
    return spot_id


def _make_jpeg():
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return ("photo.jpg", buf, "image/jpeg")


def _submit(client, spot_id, headers, **overrides):
    data = {"overall_rating": "4"}
    data.update(overrides)
    r = client.post(
        f"/spots/{spot_id}/reviews",
        data=data,
        files=[("photos", _make_jpeg())],
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestAiSummaryExposure:
    def test_spot_response_includes_ai_summary_field(self, client, auth_with_uid):
        """GET /spots/{id} surfaces ai_summary (null when none generated)."""
        spot_id = _seed_spot()
        _submit(client, spot_id, auth_with_uid["headers"])

        body = client.get(f"/spots/{spot_id}", headers=auth_with_uid["headers"]).json()
        assert "ai_summary" in body
        assert body["ai_summary"] is None

    def test_spot_response_returns_existing_summary(self, client, auth_with_uid):
        """A pre-existing ai_summary is returned verbatim on the detail endpoint."""
        spot_id = _seed_spot(ai_summary="Photographers love the dawn light here.")
        _submit(client, spot_id, auth_with_uid["headers"])

        body = client.get(f"/spots/{spot_id}", headers=auth_with_uid["headers"]).json()
        assert body["ai_summary"] == "Photographers love the dawn light here."


class TestAiSummaryPreservation:
    def test_summary_survives_delete_review_rebuild(self, client, auth_headers_for):
        """Deleting a non-last review rebuilds aggregates but keeps ai_summary."""
        from app.core.firebase import db

        spot_id = _seed_spot()
        user_a = auth_headers_for(email="a@example.com")
        user_b = auth_headers_for(email="b@example.com")

        _submit(client, spot_id, user_a["headers"], overall_rating="5")
        review_b = _submit(client, spot_id, user_b["headers"], overall_rating="3")

        # Stamp a summary directly (simulates a prior generation).
        db.collection("spots").document(spot_id).set(
            {"ai_summary": "A scenic spot.", "ai_summary_review_count": 2},
            merge=True,
        )

        # Delete one review (spot survives with one remaining).
        d = client.delete(f"/reviews/{review_b['id']}", headers=user_b["headers"])
        assert d.status_code == 204

        spot = db.collection("spots").document(spot_id).get().to_dict()
        assert spot["ai_summary"] == "A scenic spot."
        assert spot["ai_summary_review_count"] == 2
        # Aggregates were genuinely rebuilt from the survivor.
        assert spot["review_count"] == 1
        assert spot["avg_rating"] == 5.0
