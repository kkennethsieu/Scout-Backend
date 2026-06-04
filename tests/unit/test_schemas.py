"""Unit tests for Pydantic schemas and model-level validation.

Validation now happens at the Pydantic boundary (ReviewBase/ReviewCreate),
so these tests exercise the Literal vocabularies, optionality, and field
constraints directly instead of the old validate_enum() helpers.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.error import ErrorResponse
from app.schemas.pagination import PaginatedReviews
from app.schemas.review import ReviewBase, ReviewResponse
from app.schemas.spot import SpotResponse
from app.schemas.user import UserResponse


class TestReviewBaseValidation:
    """Literal vocabularies, optionality, and constraints on review content."""

    def test_minimal_only_rating(self):
        """Everything except overall_rating is optional and defaults to None/empty."""
        r = ReviewBase(overall_rating=4)
        assert r.overall_rating == 4
        assert r.notes is None
        assert r.access_level is None
        assert r.best_time_of_day == []
        assert r.best_season == []
        assert r.permit_required is None  # tristate: unanswered

    def test_overall_rating_required(self):
        with pytest.raises(ValidationError):
            ReviewBase()

    @pytest.mark.parametrize("rating", [0, 6, -1])
    def test_overall_rating_bounds(self, rating):
        with pytest.raises(ValidationError):
            ReviewBase(overall_rating=rating)

    @pytest.mark.parametrize("value", ["Easy", "Moderate", "Difficult"])
    def test_valid_access_level(self, value):
        assert ReviewBase(overall_rating=3, access_level=value).access_level == value

    @pytest.mark.parametrize("value", ["easy", "Hard", "EASY"])
    def test_invalid_access_level(self, value):
        with pytest.raises(ValidationError):
            ReviewBase(overall_rating=3, access_level=value)

    def test_valid_best_season(self):
        r = ReviewBase(overall_rating=3, best_season=["Spring", "YearRound"])
        assert r.best_season == ["Spring", "YearRound"]

    def test_invalid_best_season(self):
        with pytest.raises(ValidationError):
            ReviewBase(overall_rating=3, best_season=["spring"])

    def test_valid_best_time_of_day(self):
        r = ReviewBase(overall_rating=3, best_time_of_day=["Sunrise", "GoldenHour"])
        assert r.best_time_of_day == ["Sunrise", "GoldenHour"]

    def test_invalid_best_time_of_day(self):
        with pytest.raises(ValidationError):
            ReviewBase(overall_rating=3, best_time_of_day=["Sunset"])  # not in vocab

    @pytest.mark.parametrize("value", [True, False, None])
    def test_tristate_booleans(self, value):
        r = ReviewBase(overall_rating=3, permit_required=value)
        assert r.permit_required is value

    def test_text_field_length_cap(self):
        ReviewBase(overall_rating=3, notes="x" * 2000)  # ok at limit
        with pytest.raises(ValidationError):
            ReviewBase(overall_rating=3, notes="x" * 2001)

    def test_no_environment_field(self):
        """environment is gone — passing it is silently ignored, not stored."""
        r = ReviewBase(overall_rating=3, environment="Urban")
        assert not hasattr(r, "environment")


class TestUserResponseSchema:
    def test_valid_user(self):
        user = UserResponse(
            uid="abc123",
            email="test@example.com",
            display_name="Test User",
            photo_url="https://example.com/photo.jpg",
            created_at=datetime.now(timezone.utc),
        )
        assert user.uid == "abc123"

    def test_null_photo_url(self):
        user = UserResponse(
            uid="abc123",
            email="test@example.com",
            display_name="Test User",
            photo_url=None,
            created_at=datetime.now(timezone.utc),
        )
        assert user.photo_url is None


class TestSpotResponseSchema:
    def test_valid_spot(self):
        spot = SpotResponse(
            id="spot-1",
            name="Test Spot",
            public_lat=34.0522,
            public_lng=-118.2437,
            city="Los Angeles",
            admin_area="California",
            country="United States",
            created_at=datetime.now(timezone.utc),
            review_count=5,
            avg_rating=4.2,
            mode_access_level="Easy",
            mode_entrance_fee="Free",
            mode_crowd_level="Light",
            best_times=["GoldenHour", "Sunrise"],
            best_seasons=["Spring", "Fall"],
            mode_permit_required=False,
            mode_drone_allowed=False,
            mode_tripod_allowed=True,
            recent_gear_recommendations=["Tripod is crucial"],
            recent_composition_hints=["Frame with arch"],
            recent_review_photos=[],
        )
        assert spot.id == "spot-1"
        assert spot.best_seasons == ["Spring", "Fall"]

    def test_mode_fields_optional(self):
        """A spot whose reviews never answered the enum fields → mode_* is None."""
        spot = SpotResponse(
            id="spot-1",
            name="Test Spot",
            public_lat=0.0,
            public_lng=0.0,
            city="X",
            admin_area="Y",
            country="Z",
            created_at=datetime.now(timezone.utc),
            review_count=1,
            avg_rating=4.0,
        )
        assert spot.mode_access_level is None
        assert spot.best_seasons == []


class TestReviewResponseSchema:
    def test_valid_review(self):
        review = ReviewResponse(
            id="rev-1",
            spot_id="spot-1",
            user_id="user-1",
            photo_urls=["https://example.com/photo.jpg"],
            overall_rating=4,
            notes="Great spot!",
            best_time_of_day=["Sunrise", "GoldenHour"],
            best_season=["Summer"],
            access_level="Easy",
            entrance_fee="Free",
            crowd_level="Light",
            permit_required=False,
            drone_allowed=None,
            tripod_allowed=True,
            gear_recommendations="Wide angle lens",
            composition_hints="Get low for foreground",
            created_at=datetime.now(timezone.utc),
        )
        assert review.overall_rating == 4
        assert review.drone_allowed is None

    def test_photo_urls_min_one(self):
        with pytest.raises(ValidationError):
            ReviewResponse(
                id="rev-1",
                spot_id="spot-1",
                user_id="user-1",
                photo_urls=[],
                overall_rating=4,
                created_at=datetime.now(timezone.utc),
            )

    def test_photo_urls_max_ten(self):
        with pytest.raises(ValidationError):
            ReviewResponse(
                id="rev-1",
                spot_id="spot-1",
                user_id="user-1",
                photo_urls=[f"u{i}" for i in range(11)],
                overall_rating=4,
                created_at=datetime.now(timezone.utc),
            )


class TestPaginatedReviewsSchema:
    def test_empty_page(self):
        page = PaginatedReviews(items=[], limit=20, next_cursor=None)
        assert page.items == []
        assert page.next_cursor is None

    def test_with_cursor(self):
        page = PaginatedReviews(items=[], limit=20, next_cursor="abc123")
        assert page.next_cursor == "abc123"


class TestErrorResponseSchema:
    def test_error(self):
        err = ErrorResponse(detail="Not found", code="SPOT_NOT_FOUND")
        assert err.code == "SPOT_NOT_FOUND"


class TestSpotAlreadyExistsException:
    """Test SpotAlreadyExists exception structure."""

    def test_exception_payload(self):
        from app.core.exceptions import SpotAlreadyExists

        exc = SpotAlreadyExists(spot_id="test-id", name="Scenic Spot", distance_m=12.3)
        assert exc.status == 409
        assert exc.code == "SPOT_ALREADY_EXISTS"
        assert "Scenic Spot" in exc.detail
        assert exc.payload["spot_id"] == "test-id"
        assert exc.payload["name"] == "Scenic Spot"
        assert exc.payload["distance_m"] == 12.3
