"""Unit tests for geocoding._parse_components.

Tests the one-pass component parser with various Google Geocoding API
response shapes. No network calls — pure function tests.
"""

from app.services.geocoding import _parse_components


def _make_body(components):
    """Helper to wrap address_components in the Google response shape."""
    return {"results": [{"address_components": components}]}


class TestParseComponents:
    """Test _parse_components with various response shapes."""

    def test_us_response(self):
        """US response → locality + state + country."""
        body = _make_body(
            [
                {"long_name": "Los Angeles", "types": ["locality"]},
                {
                    "long_name": "California",
                    "types": ["administrative_area_level_1"],
                },
                {"long_name": "United States", "types": ["country"]},
            ]
        )
        result = _parse_components(body)
        assert result == {
            "city": "Los Angeles",
            "admin_area": "California",
            "country": "United States",
        }

    def test_sublocality_before_locality(self):
        """
        Sublocality appears before locality in array → still returns locality.
        This is the ordering-bug regression test.
        """
        body = _make_body(
            [
                {"long_name": "Downtown", "types": ["sublocality"]},
                {"long_name": "Los Angeles", "types": ["locality"]},
                {
                    "long_name": "California",
                    "types": ["administrative_area_level_1"],
                },
                {"long_name": "United States", "types": ["country"]},
            ]
        )
        result = _parse_components(body)
        assert result["city"] == "Los Angeles"  # NOT "Downtown"

    def test_jp_response(self):
        """Japanese response → locality + prefecture."""
        body = _make_body(
            [
                {"long_name": "Shibuya", "types": ["locality"]},
                {
                    "long_name": "Tokyo",
                    "types": ["administrative_area_level_1"],
                },
                {"long_name": "Japan", "types": ["country"]},
            ]
        )
        result = _parse_components(body)
        assert result == {
            "city": "Shibuya",
            "admin_area": "Tokyo",
            "country": "Japan",
        }

    def test_uk_postal_town_fallback(self):
        """UK response → falls back to postal_town when no locality."""
        body = _make_body(
            [
                {"long_name": "London", "types": ["postal_town"]},
                {
                    "long_name": "England",
                    "types": ["administrative_area_level_1"],
                },
                {"long_name": "United Kingdom", "types": ["country"]},
            ]
        )
        result = _parse_components(body)
        assert result["city"] == "London"

    def test_sublocality_fallback(self):
        """When only sublocality is available, use it."""
        body = _make_body(
            [
                {"long_name": "Gangnam-gu", "types": ["sublocality"]},
                {
                    "long_name": "Seoul",
                    "types": ["administrative_area_level_1"],
                },
                {"long_name": "South Korea", "types": ["country"]},
            ]
        )
        result = _parse_components(body)
        assert result["city"] == "Gangnam-gu"

    def test_missing_all_city_candidates(self):
        """No locality, sublocality, or postal_town → empty string."""
        body = _make_body(
            [
                {
                    "long_name": "California",
                    "types": ["administrative_area_level_1"],
                },
                {"long_name": "United States", "types": ["country"]},
            ]
        )
        result = _parse_components(body)
        assert result["city"] == ""

    def test_empty_results(self):
        """Empty results array → all empty strings."""
        body = {"results": []}
        result = _parse_components(body)
        assert result == {"city": "", "admin_area": "", "country": ""}

    def test_empty_address_components(self):
        """No address_components → all empty strings."""
        body = {"results": [{"address_components": []}]}
        result = _parse_components(body)
        assert result == {"city": "", "admin_area": "", "country": ""}

    def test_locality_preferred_over_postal_town(self):
        """When both locality and postal_town exist, locality wins."""
        body = _make_body(
            [
                {"long_name": "Manchester", "types": ["postal_town"]},
                {"long_name": "Salford", "types": ["locality"]},
                {
                    "long_name": "England",
                    "types": ["administrative_area_level_1"],
                },
                {"long_name": "United Kingdom", "types": ["country"]},
            ]
        )
        result = _parse_components(body)
        assert result["city"] == "Salford"  # locality wins
