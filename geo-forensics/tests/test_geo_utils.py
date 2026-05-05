"""Tests for geo_utils module."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.geo_utils import itm_to_wgs84, wgs84_to_itm, calc_distance, point_in_polygon


class TestITMConversion:
    """Test ITM <-> WGS84 conversion."""

    def test_tel_aviv_area(self):
        """ITM coords near Tel Aviv should give reasonable WGS84."""
        lat, lon = itm_to_wgs84(200000, 660000)
        assert 32.0 < lat < 32.2
        assert 34.7 < lon < 35.1

    def test_haifa_area(self):
        """ITM coords near Haifa should give reasonable WGS84."""
        lat, lon = itm_to_wgs84(200000, 740000)
        assert 32.7 < lat < 32.9
        assert 34.9 < lon < 35.1

    def test_roundtrip(self):
        """Converting ITM->WGS84->ITM should return original coords."""
        x_orig, y_orig = 200000, 660000
        lat, lon = itm_to_wgs84(x_orig, y_orig)
        x_back, y_back = wgs84_to_itm(lat, lon)
        assert abs(x_back - x_orig) < 1  # Less than 1 meter error
        assert abs(y_back - y_orig) < 1

    def test_invalid_x_raises(self):
        """X outside Israel range should raise ValueError."""
        with pytest.raises(ValueError, match="X="):
            itm_to_wgs84(50000, 660000)

    def test_invalid_y_raises(self):
        """Y outside Israel range should raise ValueError."""
        with pytest.raises(ValueError, match="Y="):
            itm_to_wgs84(200000, 100000)


class TestDistance:
    """Test Haversine distance calculation."""

    def test_same_point(self):
        """Distance from a point to itself should be 0."""
        d = calc_distance(32.0, 34.8, 32.0, 34.8)
        assert d == 0.0

    def test_known_distance(self):
        """Tel Aviv to Haifa is roughly 80-90 km."""
        d = calc_distance(32.08, 34.78, 32.82, 34.99)
        assert 80_000 < d < 95_000


class TestPointInPolygon:
    """Test point-in-polygon check."""

    def test_point_inside_square(self):
        """Point in center of square should be inside."""
        square = [(0, 0), (0, 10), (10, 10), (10, 0)]
        assert point_in_polygon(5, 5, square) is True

    def test_point_outside_square(self):
        """Point outside square should be outside."""
        square = [(0, 0), (0, 10), (10, 10), (10, 0)]
        assert point_in_polygon(15, 15, square) is False
