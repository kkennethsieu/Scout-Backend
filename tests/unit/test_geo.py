"""Unit tests for geo.py — haversine distance and bounding box.

Pure math, no Firebase dependency.
"""

import pytest

from app.services.geo import bounding_box, haversine_km


class TestHaversine:
    """Test haversine distance calculation."""

    def test_la_to_sf(self):
        """LA to SF ≈ 559 km."""
        # Los Angeles: 34.0522, -118.2437
        # San Francisco: 37.7749, -122.4194
        d = haversine_km(34.0522, -118.2437, 37.7749, -122.4194)
        assert 550 < d < 570, f"LA→SF should be ~559km, got {d}"

    def test_same_point(self):
        """Same point → 0 km."""
        d = haversine_km(34.0522, -118.2437, 34.0522, -118.2437)
        assert d == pytest.approx(0.0, abs=1e-10)

    def test_equator_one_degree(self):
        """One degree of longitude at the equator ≈ 111 km."""
        d = haversine_km(0, 0, 0, 1)
        assert 110 < d < 113

    def test_short_distance(self):
        """Two nearby points in LA ≈ small distance."""
        # UCLA: 34.0689, -118.4452
        # Santa Monica Pier: 34.0094, -118.4973
        d = haversine_km(34.0689, -118.4452, 34.0094, -118.4973)
        assert 5 < d < 10

    def test_new_york_to_london(self):
        """NYC to London ≈ 5,570 km."""
        d = haversine_km(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5500 < d < 5650

    def test_symmetry(self):
        """Distance A→B == distance B→A."""
        d1 = haversine_km(34.0522, -118.2437, 37.7749, -122.4194)
        d2 = haversine_km(37.7749, -122.4194, 34.0522, -118.2437)
        assert d1 == pytest.approx(d2, abs=1e-10)


class TestBoundingBox:
    """Test bounding box calculation."""

    def test_basic_box(self):
        """Basic bounding box at mid-latitude."""
        min_lat, max_lat, min_lng, max_lng = bounding_box(34.0, -118.0, 10.0)

        # Should be roughly symmetric around center
        assert min_lat < 34.0 < max_lat
        assert min_lng < -118.0 < max_lng

        # 10km ≈ 0.09° latitude
        lat_range = max_lat - min_lat
        assert 0.15 < lat_range < 0.25

    def test_small_radius(self):
        """Very small radius → tight box."""
        min_lat, max_lat, min_lng, max_lng = bounding_box(34.0, -118.0, 0.1)
        assert max_lat - min_lat < 0.01
        assert max_lng - min_lng < 0.02

    def test_equator_symmetry(self):
        """At equator, lat and lng ranges should be similar."""
        min_lat, max_lat, min_lng, max_lng = bounding_box(0, 0, 10.0)
        lat_range = max_lat - min_lat
        lng_range = max_lng - min_lng
        # At equator, 1° lat ≈ 1° lng, so ranges should be close
        assert abs(lat_range - lng_range) < 0.01

    def test_high_latitude_lng_expansion(self):
        """At high latitudes, longitude range should be wider than latitude range."""
        min_lat, max_lat, min_lng, max_lng = bounding_box(60, 0, 10.0)
        lat_range = max_lat - min_lat
        lng_range = max_lng - min_lng
        # At 60°, cos(60°) = 0.5, so lng_range ≈ 2x lat_range
        assert lng_range > lat_range * 1.5

    def test_contains_center(self):
        """Bounding box always contains the center point."""
        for lat, lng in [(0, 0), (34, -118), (60, 25), (-33, 151)]:
            min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, 5.0)
            assert min_lat <= lat <= max_lat
            assert min_lng <= lng <= max_lng
