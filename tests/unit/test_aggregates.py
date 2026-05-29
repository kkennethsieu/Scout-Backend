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
    permit_required=False,
    drone_allowed=False,
    tripod_allowed=False,
    gear_recommendations="",
    composition_hints="",
    best_time_of_day=None,
):
    """Helper to build a review dict for testing."""
    return {
        "overall_rating": rating,
        "access_level": access,
        "entrance_fee": fee,
        "crowd_level": crowd,
        "environment": env,
        "photo_urls": [photo_url],
        "permit_required": permit_required,
        "drone_allowed": drone_allowed,
        "tripod_allowed": tripod_allowed,
        "gear_recommendations": gear_recommendations,
        "composition_hints": composition_hints,
        "best_time_of_day": best_time_of_day if best_time_of_day is not None else ["Sunrise"],
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
        assert agg["best_time_of_day_counts"] == {}
        assert agg["best_times"] == []
        assert agg["permit_required_counts"] == {}
        assert agg["drone_allowed_counts"] == {}
        assert agg["tripod_allowed_counts"] == {}
        assert agg["mode_permit_required"] is None
        assert agg["mode_drone_allowed"] is None
        assert agg["mode_tripod_allowed"] is None
        assert agg["recent_gear_recommendations"] == []
        assert agg["recent_composition_hints"] == []

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

    def test_best_times_aggregation_and_sorting(self):
        """best_times aggregates counts and sorts by count (descending) then alphabetically."""
        spot = {"name": "Test", **empty_aggregates()}

        # 3 votes for GoldenHour, 2 for Sunset, 2 for Sunrise, 1 for Night
        spot = update_or_init_aggregates(
            spot, _make_review(best_time_of_day=["GoldenHour", "Sunset"]), "rev-0"
        )
        spot = update_or_init_aggregates(
            spot, _make_review(best_time_of_day=["GoldenHour", "Sunrise"]), "rev-1"
        )
        spot = update_or_init_aggregates(
            spot,
            _make_review(best_time_of_day=["GoldenHour", "Sunset", "Sunrise", "Night"]),
            "rev-2",
        )

        counts = spot["best_time_of_day_counts"]
        assert counts["GoldenHour"] == 3
        assert counts["Sunset"] == 2
        assert counts["Sunrise"] == 2
        assert counts["Night"] == 1

        # Sorted by count desc, then alphabetically: GoldenHour (3), Sunrise (2), Sunset (2), Night (1)
        # Sunrise < Sunset alphabetically.
        assert spot["best_times"] == ["GoldenHour", "Sunrise", "Sunset", "Night"]

    def test_boolean_modes_majority_and_ties(self):
        """Boolean aggregates select majority, tie-break legally (permit->True, drone->False, tripod->False)."""
        spot = {"name": "Test", **empty_aggregates()}

        # Vote 1: permit=True, drone=True, tripod=True
        spot = update_or_init_aggregates(
            spot,
            _make_review(permit_required=True, drone_allowed=True, tripod_allowed=True),
            "rev-1",
        )
        assert spot["mode_permit_required"] is True
        assert spot["mode_drone_allowed"] is True
        assert spot["mode_tripod_allowed"] is True

        # Vote 2: permit=False, drone=False, tripod=False (TIE)
        spot = update_or_init_aggregates(
            spot,
            _make_review(permit_required=False, drone_allowed=False, tripod_allowed=False),
            "rev-2",
        )
        # Tie-breaks:
        # permit_required -> True (fail-safe for legal reasons)
        # drone_allowed -> False (fail-safe for legal reasons)
        # tripod_allowed -> False (fail-safe)
        assert spot["mode_permit_required"] is True
        assert spot["mode_drone_allowed"] is False
        assert spot["mode_tripod_allowed"] is False

        # Vote 3: permit=False, drone=False, tripod=False (False majority)
        spot = update_or_init_aggregates(
            spot,
            _make_review(permit_required=False, drone_allowed=False, tripod_allowed=False),
            "rev-3",
        )
        assert spot["mode_permit_required"] is False
        assert spot["mode_drone_allowed"] is False
        assert spot["mode_tripod_allowed"] is False

    def test_textual_aggregates_prepend_and_cap(self):
        """Textual aggregates prepend new entries, cap at 5, ignore empty tips."""
        spot = {"name": "Test", **empty_aggregates()}

        # 1. First review with tips
        spot = update_or_init_aggregates(
            spot,
            _make_review(
                gear_recommendations="Tripod is key", composition_hints="Use leading lines"
            ),
            "rev-1",
        )
        assert spot["recent_gear_recommendations"] == ["Tripod is key"]
        assert spot["recent_composition_hints"] == ["Use leading lines"]

        # 2. Review without tips (should be ignored, keeping previous)
        spot = update_or_init_aggregates(
            spot, _make_review(gear_recommendations="", composition_hints=" "), "rev-2"
        )
        assert spot["recent_gear_recommendations"] == ["Tripod is key"]
        assert spot["recent_composition_hints"] == ["Use leading lines"]

        # 3. Add more tips to verify prepend order and capping
        for i in range(5):
            spot = update_or_init_aggregates(
                spot,
                _make_review(gear_recommendations=f"Gear {i}", composition_hints=f"Comp {i}"),
                f"rev-tip-{i}",
            )

        # Prepend order: Gear 4 is newest, Gear 0 is oldest, "Tripod is key" is oldest and got capped (since limit is 5)
        assert len(spot["recent_gear_recommendations"]) == 5
        assert spot["recent_gear_recommendations"][0] == "Gear 4"
        assert spot["recent_gear_recommendations"][4] == "Gear 0"
        assert "Tripod is key" not in spot["recent_gear_recommendations"]
