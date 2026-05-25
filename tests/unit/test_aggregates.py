"""Unit tests for aggregates.py — incremental aggregate computation.

Pure functions, no Firebase dependency. Target: ~100% coverage.
"""

from datetime import datetime, timezone

import pytest

from app.services.aggregates import empty_aggregates, update_or_init_aggregates


def _make_review(
    rating=4,
    access="Easy",
    fee="Free",
    crowd="Light",
    env="Urban",
    photo_url="https://example.com/photo.jpg",
    created_at=None,
):
    """Helper to build a review dict for testing."""
    return {
        "overall_rating": rating,
        "access_level": access,
        "entrance_fee": fee,
        "crowd_level": crowd,
        "environment": env,
        "photo_urls": [photo_url],
        "created_at": created_at or datetime.now(timezone.utc),
    }


class TestEmptyAggregates:
    """Tests for the empty_aggregates factory."""

    def test_returns_correct_keys(self):
        agg = empty_aggregates()
        assert agg["review_count"] == 0
        assert agg["avg_rating"] == 0.0
        assert agg["access_level_counts"] == {}
        assert agg["entrance_fee_counts"] == {}
        assert agg["crowd_level_counts"] == {}
        assert agg["environment_counts"] == {}
        assert agg["mode_access_level"] == ""
        assert agg["mode_entrance_fee"] == ""
        assert agg["mode_crowd_level"] == ""
        assert agg["mode_environment"] == ""
        assert agg["recent_review_photos"] == []

    def test_returns_fresh_dicts(self):
        """Each call returns a new dict — mutating one doesn't affect the next."""
        a = empty_aggregates()
        b = empty_aggregates()
        a["access_level_counts"]["Easy"] = 5
        a["recent_review_photos"].append({"fake": True})
        assert b["access_level_counts"] == {}
        assert b["recent_review_photos"] == []


class TestUpdateOrInitAggregates:
    """Tests for update_or_init_aggregates."""

    def test_first_review_on_empty_spot(self):
        """First review on a spot with empty_aggregates() baseline."""
        spot = {"name": "Test Spot", **empty_aggregates()}
        review = _make_review(rating=5, access="Moderate", fee="Paid")
        result = update_or_init_aggregates(spot, review, "rev-1")

        assert result["review_count"] == 1
        assert result["avg_rating"] == 5.0
        assert result["access_level_counts"] == {"Moderate": 1}
        assert result["entrance_fee_counts"] == {"Paid": 1}
        assert result["mode_access_level"] == "Moderate"
        assert result["mode_entrance_fee"] == "Paid"
        assert len(result["recent_review_photos"]) == 1
        assert result["recent_review_photos"][0]["review_id"] == "rev-1"

    def test_incremental_avg_rating(self):
        """avg_rating across [5, 3, 4] → 4.0."""
        spot = {"name": "Test", **empty_aggregates()}
        reviews = [
            _make_review(rating=5),
            _make_review(rating=3),
            _make_review(rating=4),
        ]
        for i, r in enumerate(reviews):
            spot = update_or_init_aggregates(spot, r, f"rev-{i}")

        assert spot["review_count"] == 3
        assert spot["avg_rating"] == pytest.approx(4.0)

    def test_mode_reflects_majority(self):
        """5th review with mixed values → mode reflects majority."""
        spot = {"name": "Test", **empty_aggregates()}

        # 3× "Easy", 1× "Moderate", 1× "Difficult"
        for i in range(3):
            spot = update_or_init_aggregates(spot, _make_review(access="Easy"), f"rev-{i}")
        spot = update_or_init_aggregates(spot, _make_review(access="Moderate"), "rev-3")
        spot = update_or_init_aggregates(spot, _make_review(access="Difficult"), "rev-4")

        assert spot["mode_access_level"] == "Easy"
        assert spot["access_level_counts"]["Easy"] == 3

    def test_tie_break_alphabetical(self):
        """Tie-break: 2× "Easy" + 2× "Moderate" → "Easy" (alphabetical)."""
        spot = {"name": "Test", **empty_aggregates()}

        spot = update_or_init_aggregates(spot, _make_review(access="Easy"), "rev-0")
        spot = update_or_init_aggregates(spot, _make_review(access="Moderate"), "rev-1")
        spot = update_or_init_aggregates(spot, _make_review(access="Easy"), "rev-2")
        spot = update_or_init_aggregates(spot, _make_review(access="Moderate"), "rev-3")

        assert spot["access_level_counts"]["Easy"] == 2
        assert spot["access_level_counts"]["Moderate"] == 2
        # Alphabetical tie-break: "Easy" < "Moderate"
        assert spot["mode_access_level"] == "Easy"

    def test_recent_photos_cap_at_5(self):
        """7 reviews → recent_review_photos has newest 5, reverse chronological."""
        spot = {"name": "Test", **empty_aggregates()}

        for i in range(7):
            ts = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
            review = _make_review(photo_url=f"https://example.com/photo-{i}.jpg", created_at=ts)
            spot = update_or_init_aggregates(spot, review, f"rev-{i}")

        photos = spot["recent_review_photos"]
        assert len(photos) == 5

        # Newest should be first (rev-6), oldest in the list should be rev-2
        assert photos[0]["review_id"] == "rev-6"
        assert photos[4]["review_id"] == "rev-2"

    def test_does_not_mutate_input(self):
        """update_or_init_aggregates returns a new dict, doesn't mutate input."""
        spot = {"name": "Test", **empty_aggregates()}
        original_count = spot["review_count"]
        review = _make_review()
        result = update_or_init_aggregates(spot, review, "rev-0")

        assert spot["review_count"] == original_count  # original unchanged
        assert result["review_count"] == 1

    def test_all_mode_fields_updated(self):
        """All four mode fields update correctly."""
        spot = {"name": "Test", **empty_aggregates()}
        review = _make_review(access="Difficult", fee="Permit", crowd="Crowded", env="Coastal")
        result = update_or_init_aggregates(spot, review, "rev-0")

        assert result["mode_access_level"] == "Difficult"
        assert result["mode_entrance_fee"] == "Permit"
        assert result["mode_crowd_level"] == "Crowded"
        assert result["mode_environment"] == "Coastal"
