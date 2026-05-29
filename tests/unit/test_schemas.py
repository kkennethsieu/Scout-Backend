"""Unit tests for Pydantic schemas and enum validation."""

from datetime import datetime, timezone

import pytest

from app.core.exceptions import InvalidEnumValue
from app.schemas.enums import validate_enum, validate_enum_list
from app.schemas.error import ErrorResponse
from app.schemas.pagination import PaginatedReviews
from app.schemas.review import ReviewResponse
from app.schemas.spot import SpotResponse
from app.schemas.user import UserResponse


class TestEnumValidation:
    """Test explicit enum validation."""

    def test_valid_access_level(self):
        assert validate_enum("access_level", "Easy") == "Easy"
        assert validate_enum("access_level", "Moderate") == "Moderate"
        assert validate_enum("access_level", "Difficult") == "Difficult"

    def test_invalid_access_level(self):
        with pytest.raises(InvalidEnumValue):
            validate_enum("access_level", "easy")  # lowercase

    def test_invalid_access_level_unknown(self):
        with pytest.raises(InvalidEnumValue):
            validate_enum("access_level", "Hard")

    def test_valid_best_time_list(self):
        result = validate_enum_list("best_time_of_day", ["Sunrise", "GoldenHour"])
        assert result == ["Sunrise", "GoldenHour"]

    def test_invalid_best_time_list(self):
        with pytest.raises(InvalidEnumValue):
            validate_enum_list("best_time_of_day", ["Sunrise", "morning"])

    def test_valid_environment(self):
        for v in ["Urban", "Nature", "Coastal", "Mountain", "Desert", "Indoor"]:
            assert validate_enum("environment", v) == v

    def test_valid_crowd_level(self):
        for v in ["Empty", "Light", "Moderate", "Crowded"]:
            assert validate_enum("crowd_level", v) == v

    def test_valid_entrance_fee(self):
        for v in ["Free", "Paid", "Permit"]:
            assert validate_enum("entrance_fee", v) == v


class TestUserResponseSchema:
    """Test UserResponse schema."""

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
    """Test SpotResponse schema."""

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
            mode_environment="Urban",
            best_times=["GoldenHour", "Sunrise"],
            mode_permit_required=False,
            mode_drone_allowed=False,
            mode_tripod_allowed=True,
            recent_gear_recommendations=["Tripod is crucial"],
            recent_composition_hints=["Frame with arch"],
            recent_review_photos=[],
        )
        assert spot.id == "spot-1"
        assert spot.avg_rating == 4.2


class TestReviewResponseSchema:
    """Test ReviewResponse schema."""

    def test_valid_review(self):
        review = ReviewResponse(
            id="rev-1",
            spot_id="spot-1",
            user_id="user-1",
            photo_urls=["https://example.com/photo.jpg"],
            overall_rating=4,
            notes="Great spot!",
            best_time_of_day=["Sunrise", "GoldenHour"],
            access_level="Easy",
            entrance_fee="Free",
            crowd_level="Light",
            environment="Urban",
            permit_required=False,
            drone_allowed=False,
            tripod_allowed=True,
            gear_recommendations="Wide angle lens",
            composition_hints="Get low for foreground",
            created_at=datetime.now(timezone.utc),
        )
        assert review.overall_rating == 4


class TestPaginatedReviewsSchema:
    """Test PaginatedReviews schema."""

    def test_empty_page(self):
        page = PaginatedReviews(items=[], limit=20, next_cursor=None)
        assert page.items == []
        assert page.next_cursor is None

    def test_with_cursor(self):
        page = PaginatedReviews(items=[], limit=20, next_cursor="abc123")
        assert page.next_cursor == "abc123"


class TestErrorResponseSchema:
    """Test ErrorResponse schema."""

    def test_error(self):
        err = ErrorResponse(detail="Not found", code="SPOT_NOT_FOUND")
        assert err.code == "SPOT_NOT_FOUND"
