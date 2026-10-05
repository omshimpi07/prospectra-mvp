"""Deterministic city centroid registry and geographic bounding box calculations.

Provides known coordinate centroids for supported metropolitan areas and calculates
spatial bounding boxes for Overture GeoParquet queries without requiring an external geocoder.
"""

import math
from typing import Final

from backend.middleware.errors import AppError

# Centroid mapping: normalized city name -> (latitude, longitude)
CITY_CENTROIDS: Final[dict[str, tuple[float, float]]] = {
    "pune": (18.5204, 73.8567),
    "mumbai": (19.0760, 72.8777),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "delhi": (28.6139, 77.2090),
    "new_delhi": (28.6139, 77.2090),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "surat": (21.1702, 72.8311),
    "lucknow": (26.8467, 80.9462),
    "nagpur": (21.1458, 79.0882),
    "indore": (22.7196, 75.8577),
    "thane": (19.2183, 72.9781),
    "bhopal": (23.2599, 77.4126),
    "visakhapatnam": (17.6868, 83.2185),
    "pimpri_chinchwad": (18.6298, 73.7997),
    "patna": (25.5941, 85.1376),
    "vadodara": (22.3072, 73.1812),
    "ghaziabad": (28.6692, 77.4538),
    "ludhiana": (30.9010, 75.8573),
    "agra": (27.1767, 78.0081),
    "nashik": (19.9975, 73.7898),
    "noida": (28.5355, 77.3910),
    "gurgaon": (28.4595, 77.0266),
    "gurugram": (28.4595, 77.0266),
    "goa": (15.4909, 73.8278),
    "panaji": (15.4909, 73.8278),
    "chandigarh": (30.7333, 76.7794),
}


def normalize_city_name(city: str) -> str:
    """Normalize city string for dictionary lookup."""
    return city.strip().lower().replace("-", "_").replace(" ", "_")


def get_city_centroid(city: str) -> tuple[float, float]:
    """Retrieve latitude and longitude for a supported city.

    Raises AppError(422, 'UNSUPPORTED_CITY') if city is not in the centroid registry.
    """
    normalized = normalize_city_name(city)
    centroid = CITY_CENTROIDS.get(normalized)
    if not centroid:
        raise AppError(
            "UNSUPPORTED_CITY",
            f"City '{city}' is not currently supported in the centroid registry. "
            f"Supported cities include: {', '.join(sorted(CITY_CENTROIDS.keys())[:8])}...",
            status_code=422,
        )
    return centroid


def calculate_bounding_box(
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> tuple[float, float, float, float]:
    """Calculate geographic bounding box (min_lat, max_lat, min_lon, max_lon) for a center point.

    Uses spherical approximation where 1 degree latitude ~= 111.0 km,
    and 1 degree longitude ~= 111.0 * cos(lat) km.
    """
    lat_delta = radius_km / 111.0
    lat_rad = math.radians(center_lat)
    cos_lat = math.cos(lat_rad)
    # Guard against extreme polar latitudes
    lon_delta = radius_km / (111.0 * max(cos_lat, 0.01))

    min_lat = max(-90.0, center_lat - lat_delta)
    max_lat = min(90.0, center_lat + lat_delta)
    min_lon = max(-180.0, center_lon - lon_delta)
    max_lon = min(180.0, center_lon + lon_delta)

    return (min_lat, max_lat, min_lon, max_lon)
