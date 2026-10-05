"""Unit tests for geography module and city centroid registry."""

import pytest

from backend.middleware.errors import AppError
from backend.models.geography import (
    calculate_bounding_box,
    get_city_centroid,
    normalize_city_name,
)


def test_normalize_city_name():
    assert normalize_city_name("Pune") == "pune"
    assert normalize_city_name("  New Delhi  ") == "new_delhi"
    assert normalize_city_name("Pimpri-Chinchwad") == "pimpri_chinchwad"


def test_get_city_centroid_supported():
    lat, lon = get_city_centroid("Pune")
    assert round(lat, 2) == 18.52
    assert round(lon, 2) == 73.86

    lat_m, lon_m = get_city_centroid("mumbai")
    assert round(lat_m, 2) == 19.08
    assert round(lon_m, 2) == 72.88


def test_get_city_centroid_unsupported_raises_422():
    with pytest.raises(AppError) as exc_info:
        get_city_centroid("Atlantis")
    assert exc_info.value.code == "UNSUPPORTED_CITY"
    assert exc_info.value.status_code == 422


def test_calculate_bounding_box():
    lat, lon = 18.5204, 73.8567
    radius = 25.0
    min_lat, max_lat, min_lon, max_lon = calculate_bounding_box(lat, lon, radius)

    assert min_lat < lat < max_lat
    assert min_lon < lon < max_lon
    # ~25km in latitude degrees is ~0.225 degrees
    assert 0.20 < (max_lat - lat) < 0.25
