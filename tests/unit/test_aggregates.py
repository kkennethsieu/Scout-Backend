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
    photo_url="https://example.com/photo.jpg",
    created_at=None,
    permit_required=False,
    drone_allowed=False,
    tripod_allowed=False,
    gear_recommendations="",
    composition_hints="",
    best_time_of_day=None,
    best_season=None,
):
    """Helper to build a review dict for testing."""
    return {
        "overall_rating": rating,
        "access_level": access,
        "entrance_fee": fee,
        "crowd_level": crowd,
        "photo_urls": [photo_url],
        "permit_required": permit_required,
        "drone_allowed": drone_allowed,
        "tripod_allowed": tripod_allowed,
        "gear_recommendations": gear_recommendations,
        "composition_hints": composition_hints,
        "best_time_of_day": best_time_of_day if best_time_of_day is not None else ["Sunrise"],
        "best_season": best_season if best_season is not None else ["Summer"],
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
        # Unanswered enum modes start as None (not "")
        assert agg["mode_access_level"] is None
        assert agg["mode_entrance_fee"] is None
        assert agg["mode_crowd_level"] is None
        assert agg["recent_review_photos"] == []
        assert agg["best_time_of_day_counts"] == {}
        assert agg["best_times"] == []
        assert agg["best_season_counts"] == {}
        assert agg["best_seasons"] == []
        assert agg["permit_required_counts"] == {}
        assert agg["drone_allowed_counts"] == {}
        assert agg["tripod_allowed_counts"] == {}
        assert agg["mode_permit_required"] is None
        assert agg["mode_drone_allowed"] is None
        assert agg["mode_tripod_allowed"] is None
        assert agg["recent_gear_recommendations"] == []
        assert agg["recent_composition_hints"] == []
        # environment is fully removed
        assert "environment_counts" not in agg
        assert "mode_environment" not in agg

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
        spot = {"name": "Test", **empty_aggregates()}
        for i, r in enumerate(
            [_make_review(rating=5), _make_review(rating=3), _make_review(rating=4)]
        ):
            spot = update_or_init_aggregates(spot, r, f"rev-{i}")

        assert spot["review_count"] == 3
        assert spot["avg_rating"] == pytest.approx(4.0)

    def test_mode_reflects_majority(self):
        spot = {"name": "Test", **empty_aggregates()}
        for i in range(3):
            spot = update_or_init_aggregates(spot, _make_review(access="Easy"), f"rev-{i}")
        spot = update_or_init_aggregates(spot, _make_review(access="Moderate"), "rev-3")
        spot = update_or_init_aggregates(spot, _make_review(access="Difficult"), "rev-4")

        assert spot["mode_access_level"] == "Easy"
        assert spot["access_level_counts"]["Easy"] == 3

    def test_tie_break_alphabetical(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(spot, _make_review(access="Easy"), "rev-0")
        spot = update_or_init_aggregates(spot, _make_review(access="Moderate"), "rev-1")
        spot = update_or_init_aggregates(spot, _make_review(access="Easy"), "rev-2")
        spot = update_or_init_aggregates(spot, _make_review(access="Moderate"), "rev-3")

        assert spot["access_level_counts"]["Easy"] == 2
        assert spot["access_level_counts"]["Moderate"] == 2
        assert spot["mode_access_level"] == "Easy"

    def test_unanswered_enum_skipped_and_mode_persists(self):
        """access_level=None is not a vote: counts stay put and mode persists."""
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(spot, _make_review(access="Difficult"), "rev-0")
        assert spot["mode_access_level"] == "Difficult"

        # Second review leaves access_level unanswered
        spot = update_or_init_aggregates(spot, _make_review(access=None), "rev-1")
        assert spot["access_level_counts"] == {"Difficult": 1}
        assert spot["mode_access_level"] == "Difficult"
        assert spot["review_count"] == 2  # still counted overall

    def test_enum_mode_none_when_never_answered(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(spot, _make_review(crowd=None), "rev-0")
        assert spot["mode_crowd_level"] is None
        assert spot["crowd_level_counts"] == {}

    def test_recent_photos_cap_at_5(self):
        spot = {"name": "Test", **empty_aggregates()}
        for i in range(7):
            ts = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
            review = _make_review(photo_url=f"https://example.com/photo-{i}.jpg", created_at=ts)
            spot = update_or_init_aggregates(spot, review, f"rev-{i}")

        photos = spot["recent_review_photos"]
        assert len(photos) == 5
        assert photos[0]["review_id"] == "rev-6"
        assert photos[4]["review_id"] == "rev-2"

    def test_does_not_mutate_input(self):
        spot = {"name": "Test", **empty_aggregates()}
        review = _make_review()
        result = update_or_init_aggregates(spot, review, "rev-0")
        assert spot["review_count"] == 0
        assert result["review_count"] == 1

    def test_all_mode_fields_updated(self):
        spot = {"name": "Test", **empty_aggregates()}
        review = _make_review(access="Difficult", fee="Permit", crowd="Crowded")
        result = update_or_init_aggregates(spot, review, "rev-0")
        assert result["mode_access_level"] == "Difficult"
        assert result["mode_entrance_fee"] == "Permit"
        assert result["mode_crowd_level"] == "Crowded"

    def test_best_times_aggregation_and_sorting(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(
            spot, _make_review(best_time_of_day=["GoldenHour", "Night"]), "rev-0"
        )
        spot = update_or_init_aggregates(
            spot, _make_review(best_time_of_day=["GoldenHour", "Sunrise"]), "rev-1"
        )
        spot = update_or_init_aggregates(
            spot,
            _make_review(best_time_of_day=["GoldenHour", "Night", "Sunrise", "Midday"]),
            "rev-2",
        )

        counts = spot["best_time_of_day_counts"]
        assert counts["GoldenHour"] == 3
        assert counts["Night"] == 2
        assert counts["Sunrise"] == 2
        assert counts["Midday"] == 1
        # Count desc, then alphabetical: GoldenHour(3), Night(2), Sunrise(2), Midday(1)
        assert spot["best_times"] == ["GoldenHour", "Night", "Sunrise", "Midday"]

    def test_best_seasons_aggregation_and_sorting(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(
            spot, _make_review(best_season=["Summer", "Fall"]), "rev-0"
        )
        spot = update_or_init_aggregates(spot, _make_review(best_season=["Summer"]), "rev-1")
        spot = update_or_init_aggregates(spot, _make_review(best_season=["Winter"]), "rev-2")

        counts = spot["best_season_counts"]
        assert counts == {"Summer": 2, "Fall": 1, "Winter": 1}
        # Summer(2) first; then Fall, Winter alphabetically
        assert spot["best_seasons"] == ["Summer", "Fall", "Winter"]

    def test_empty_best_season_is_noop(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(spot, _make_review(best_season=[]), "rev-0")
        assert spot["best_seasons"] == []
        assert spot["best_season_counts"] == {}

    def test_boolean_modes_majority_and_ties(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(
            spot,
            _make_review(permit_required=True, drone_allowed=True, tripod_allowed=True),
            "rev-1",
        )
        assert spot["mode_permit_required"] is True
        assert spot["mode_drone_allowed"] is True
        assert spot["mode_tripod_allowed"] is True

        # Tie
        spot = update_or_init_aggregates(
            spot,
            _make_review(permit_required=False, drone_allowed=False, tripod_allowed=False),
            "rev-2",
        )
        assert spot["mode_permit_required"] is True  # tie-break fail-safe
        assert spot["mode_drone_allowed"] is False
        assert spot["mode_tripod_allowed"] is False

        # False majority
        spot = update_or_init_aggregates(
            spot,
            _make_review(permit_required=False, drone_allowed=False, tripod_allowed=False),
            "rev-3",
        )
        assert spot["mode_permit_required"] is False

    def test_tristate_unanswered_does_not_vote(self):
        """permit_required=None is not a vote: it stays out of the counts."""
        spot = {"name": "Test", **empty_aggregates()}
        # First review answers True
        spot = update_or_init_aggregates(spot, _make_review(permit_required=True), "rev-0")
        assert spot["mode_permit_required"] is True
        assert spot["permit_required_counts"] == {"true": 1}

        # Second review leaves it unanswered → counts unchanged, mode persists
        spot = update_or_init_aggregates(spot, _make_review(permit_required=None), "rev-1")
        assert spot["permit_required_counts"] == {"true": 1}
        assert spot["mode_permit_required"] is True

    def test_tristate_mode_none_when_never_answered(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(spot, _make_review(drone_allowed=None), "rev-0")
        assert spot["mode_drone_allowed"] is None
        assert spot["drone_allowed_counts"] == {}

    def test_textual_aggregates_prepend_and_cap(self):
        spot = {"name": "Test", **empty_aggregates()}
        spot = update_or_init_aggregates(
            spot,
            _make_review(
                gear_recommendations="Tripod is key", composition_hints="Use leading lines"
            ),
            "rev-1",
        )
        assert spot["recent_gear_recommendations"] == ["Tripod is key"]
        assert spot["recent_composition_hints"] == ["Use leading lines"]

        # Review without tips → ignored
        spot = update_or_init_aggregates(
            spot, _make_review(gear_recommendations="", composition_hints=" "), "rev-2"
        )
        assert spot["recent_gear_recommendations"] == ["Tripod is key"]

        for i in range(5):
            spot = update_or_init_aggregates(
                spot,
                _make_review(gear_recommendations=f"Gear {i}", composition_hints=f"Comp {i}"),
                f"rev-tip-{i}",
            )

        assert len(spot["recent_gear_recommendations"]) == 5
        assert spot["recent_gear_recommendations"][0] == "Gear 4"
        assert spot["recent_gear_recommendations"][4] == "Gear 0"
        assert "Tripod is key" not in spot["recent_gear_recommendations"]

    def test_none_text_fields_are_safe(self):
        """notes/gear/composition may arrive as None (optional) without error."""
        spot = {"name": "Test", **empty_aggregates()}
        review = _make_review()
        review["gear_recommendations"] = None
        review["composition_hints"] = None
        result = update_or_init_aggregates(spot, review, "rev-0")
        assert result["recent_gear_recommendations"] == []
        assert result["recent_composition_hints"] == []
