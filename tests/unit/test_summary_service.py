"""Unit tests for summary_service — AI review summary generation + debounce.

Gemini and Firestore are mocked, so these run without the emulator.
"""

from unittest.mock import MagicMock

import pytest

from app.services import summary_service


@pytest.fixture
def cfg(monkeypatch):
    """Default config: summaries on, key present, min 3 reviews, refresh every 5."""
    monkeypatch.setattr(summary_service.settings, "AI_SUMMARIES_ENABLED", True)
    monkeypatch.setattr(summary_service.settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(summary_service.settings, "AI_SUMMARY_MIN_REVIEWS", 3)
    monkeypatch.setattr(summary_service.settings, "AI_SUMMARY_REFRESH_EVERY", 5)
    monkeypatch.setattr(summary_service.settings, "GEMINI_MODEL", "test-model")


def _spot(**over):
    base = {"review_count": 5, "name": "Falls", "city": "Yosemite"}
    base.update(over)
    return base


# --- _is_due -----------------------------------------------------------------


def test_is_due_below_min_reviews(cfg):
    assert summary_service._is_due(_spot(review_count=2)) is False


def test_is_due_no_summary_yet(cfg):
    assert summary_service._is_due(_spot(review_count=3)) is True


def test_is_due_within_debounce_window(cfg):
    # Has a summary generated at count 4, now at 6 → only +2 < refresh_every(5).
    spot = _spot(review_count=6, ai_summary="x", ai_summary_review_count=4)
    assert summary_service._is_due(spot) is False


def test_is_due_past_debounce_window(cfg):
    spot = _spot(review_count=10, ai_summary="x", ai_summary_review_count=4)
    assert summary_service._is_due(spot) is True


# --- maybe_regenerate_summary ------------------------------------------------


def _patch_db(monkeypatch, spot_dict, exists=True):
    """Wire summary_service.db to return a fake spot snapshot; capture .set()."""
    snap = MagicMock()
    snap.exists = exists
    snap.to_dict.return_value = spot_dict
    ref = MagicMock()
    ref.get.return_value = snap
    db = MagicMock()
    db.collection.return_value.document.return_value = ref
    monkeypatch.setattr(summary_service, "db", db)
    return ref


def test_regenerate_writes_fields_when_due(cfg, monkeypatch):
    ref = _patch_db(monkeypatch, _spot(review_count=5))
    monkeypatch.setattr(
        summary_service.review_service,
        "_load_spot_reviews",
        lambda sid: [{"overall_rating": 5, "notes": "great"}],
    )
    monkeypatch.setattr(summary_service, "_generate", lambda prompt: "A lovely spot.")
    invalidated = MagicMock()
    monkeypatch.setattr(summary_service.spot_cache, "invalidate", invalidated)

    summary_service.maybe_regenerate_summary("spot-1")

    ref.set.assert_called_once()
    payload, kwargs = ref.set.call_args[0][0], ref.set.call_args[1]
    assert payload["ai_summary"] == "A lovely spot."
    assert payload["ai_summary_review_count"] == 5
    assert payload["ai_summary_model"] == "test-model"
    assert payload["ai_summary_generated_at"] is not None
    assert kwargs.get("merge") is True
    invalidated.assert_called_once()


def test_regenerate_noop_when_disabled(cfg, monkeypatch):
    monkeypatch.setattr(summary_service.settings, "AI_SUMMARIES_ENABLED", False)
    ref = _patch_db(monkeypatch, _spot())
    summary_service.maybe_regenerate_summary("spot-1")
    ref.get.assert_not_called()


def test_regenerate_noop_without_key(cfg, monkeypatch):
    monkeypatch.setattr(summary_service.settings, "GEMINI_API_KEY", "")
    ref = _patch_db(monkeypatch, _spot())
    summary_service.maybe_regenerate_summary("spot-1")
    ref.get.assert_not_called()


def test_regenerate_noop_when_not_due(cfg, monkeypatch):
    ref = _patch_db(monkeypatch, _spot(review_count=2))  # below min
    called = MagicMock()
    monkeypatch.setattr(summary_service, "_generate", called)
    summary_service.maybe_regenerate_summary("spot-1")
    called.assert_not_called()
    ref.set.assert_not_called()


def test_regenerate_noop_when_spot_missing(cfg, monkeypatch):
    ref = _patch_db(monkeypatch, None, exists=False)
    called = MagicMock()
    monkeypatch.setattr(summary_service, "_generate", called)
    summary_service.maybe_regenerate_summary("spot-1")
    called.assert_not_called()
    ref.set.assert_not_called()


def test_regenerate_none_spot_id_is_noop(cfg, monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(summary_service, "db", db)
    summary_service.maybe_regenerate_summary(None)
    db.collection.assert_not_called()


def test_regenerate_swallows_generation_errors(cfg, monkeypatch):
    ref = _patch_db(monkeypatch, _spot(review_count=5))
    monkeypatch.setattr(
        summary_service.review_service, "_load_spot_reviews", lambda sid: [{"overall_rating": 5}]
    )

    def boom(prompt):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(summary_service, "_generate", boom)
    # Must not raise.
    summary_service.maybe_regenerate_summary("spot-1")
    ref.set.assert_not_called()


def test_regenerate_skips_blank_summary(cfg, monkeypatch):
    ref = _patch_db(monkeypatch, _spot(review_count=5))
    monkeypatch.setattr(
        summary_service.review_service, "_load_spot_reviews", lambda sid: [{"overall_rating": 5}]
    )
    monkeypatch.setattr(summary_service, "_generate", lambda prompt: "   ")
    summary_service.maybe_regenerate_summary("spot-1")
    ref.set.assert_not_called()


# --- _build_prompt -----------------------------------------------------------


def test_build_prompt_includes_reviews_and_aggregates(cfg):
    spot = _spot(
        review_count=3,
        avg_rating=4.5,
        best_times=["Sunrise", "GoldenHour"],
        mode_permit_required=True,
        mode_drone_allowed=False,
    )
    reviews = [
        {"overall_rating": 5, "notes": "stunning at dawn", "gear_recommendations": "ND filter"},
        {"overall_rating": 4, "composition_hints": "use the foreground rocks"},
    ]
    prompt = summary_service._build_prompt(spot, reviews)
    assert "Falls" in prompt
    assert "Sunrise, GoldenHour" in prompt
    assert "Permit usually required: yes" in prompt
    assert "Drones usually allowed: no" in prompt
    assert "stunning at dawn" in prompt
    assert "use the foreground rocks" in prompt


def test_build_prompt_caps_review_count(cfg):
    spot = _spot(review_count=100)
    reviews = [{"overall_rating": 5, "notes": f"review {i}"} for i in range(60)]
    prompt = summary_service._build_prompt(spot, reviews)
    assert "review 29" in prompt  # 30th review (0-indexed) is included
    assert "review 30" not in prompt  # 31st is capped out
