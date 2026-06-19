"""Unit tests for review sort helpers (_scout_score, _sort_reviews)."""

from datetime import datetime, timedelta, timezone

from app.services.review_service import _scout_score, _sort_reviews

NOW = datetime(2026, 6, 18, tzinfo=timezone.utc)


def _review(id, rating=3, age_days=0, photos=1, notes=None, gear=None, comp=None):
    return {
        "id": id,
        "overall_rating": rating,
        "created_at": NOW - timedelta(days=age_days),
        "photo_urls": [f"p{i}" for i in range(photos)],
        "notes": notes,
        "gear_recommendations": gear,
        "composition_hints": comp,
    }


class TestScoutScore:
    def test_rich_recent_high_beats_sparse_old_low(self):
        best = _review("best", rating=5, age_days=0, photos=4, notes="a", gear="b", comp="c")
        worst = _review("worst", rating=1, age_days=365, photos=1)
        assert _scout_score(best, NOW) > _scout_score(worst, NOW)

    def test_score_in_unit_range(self):
        r = _review("r", rating=5, age_days=0, photos=4, notes="a", gear="b", comp="c")
        assert 0.0 <= _scout_score(r, NOW) <= 1.0
        # Max review: rating=1.0, recency≈1.0, richness=1.0 → ~1.0
        assert _scout_score(r, NOW) > 0.95

    def test_recency_decays(self):
        fresh = _review("fresh", rating=4, age_days=0)
        stale = _review("stale", rating=4, age_days=60)
        assert _scout_score(fresh, NOW) > _scout_score(stale, NOW)

    def test_richness_rewards_content(self):
        rich = _review("rich", rating=4, age_days=0, photos=3, notes="x", gear="y", comp="z")
        bare = _review("bare", rating=4, age_days=0, photos=1)
        assert _scout_score(rich, NOW) > _scout_score(bare, NOW)


class TestSortReviews:
    def test_newest(self):
        reviews = [_review("a", age_days=2), _review("b", age_days=0), _review("c", age_days=1)]
        _sort_reviews(reviews, "newest")
        assert [r["id"] for r in reviews] == ["b", "c", "a"]

    def test_highest_rated_ties_break_newest(self):
        reviews = [
            _review("low", rating=2, age_days=0),
            _review("high_old", rating=5, age_days=3),
            _review("high_new", rating=5, age_days=1),
        ]
        _sort_reviews(reviews, "highest_rated")
        assert [r["id"] for r in reviews] == ["high_new", "high_old", "low"]

    def test_lowest_rated_ties_break_newest(self):
        reviews = [
            _review("high", rating=5, age_days=0),
            _review("low_old", rating=1, age_days=3),
            _review("low_new", rating=1, age_days=1),
        ]
        _sort_reviews(reviews, "lowest_rated")
        assert [r["id"] for r in reviews] == ["low_new", "low_old", "high"]

    def test_scout_puts_quality_first(self):
        reviews = [
            _review("sparse", rating=2, age_days=120, photos=1),
            _review("quality", rating=5, age_days=0, photos=4, notes="a", gear="b", comp="c"),
        ]
        _sort_reviews(reviews, "scout")
        assert reviews[0]["id"] == "quality"

    def test_unknown_sort_falls_back_to_newest(self):
        reviews = [_review("a", age_days=1), _review("b", age_days=0)]
        _sort_reviews(reviews, "bogus")
        assert [r["id"] for r in reviews] == ["b", "a"]
