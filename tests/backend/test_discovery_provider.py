"""Unit tests for Discovery Provider architecture and Overture DuckDB adapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.config import Settings
from backend.middleware.errors import AppError
from backend.providers.discovery.base import DiscoveredCandidate
from backend.providers.discovery.factory import get_discovery_provider
from backend.providers.discovery.mock import MockDiscoveryProvider
from backend.providers.discovery.overture import OvertureDuckDBDiscoveryProvider
from backend.providers.discovery.taxonomy_map import map_overture_category
from backend.schemas.search import GeoBoundingBox, SearchSpecification


@pytest.fixture
def pune_search_spec() -> SearchSpecification:
    return SearchSpecification(
        target_categories=["cafe", "bakery"],
        city="Pune",
        center_lat=18.5204,
        center_lon=73.8567,
        radius_km=15.0,
        bounding_box=GeoBoundingBox(
            min_lat=18.40,
            max_lat=18.65,
            min_lon=73.75,
            max_lon=73.98,
        ),
        limit=10,
    )


def test_taxonomy_map():
    assert map_overture_category("coffee_shop") == "cafe"
    assert map_overture_category("cafe") == "cafe"
    assert map_overture_category("bakery") == "bakery"
    assert map_overture_category("hair_salon") == "salon"
    assert map_overture_category("non_existent_category_xyz") is None
    assert map_overture_category(None) is None


@pytest.mark.anyio
async def test_mock_discovery_provider(pune_search_spec: SearchSpecification):
    provider = MockDiscoveryProvider()
    candidates = await provider.discover_businesses(pune_search_spec)

    assert len(candidates) > 0
    for cand in candidates:
        assert isinstance(cand, DiscoveredCandidate)
        assert cand.canonical_category in pune_search_spec.target_categories
        assert cand.city == "Pune"


@pytest.mark.anyio
async def test_mock_discovery_provider_error_simulation(pune_search_spec: SearchSpecification):
    provider = MockDiscoveryProvider(
        error_to_raise=AppError("DISCOVERY_PROVIDER_TIMEOUT", "Timed out", status_code=504)
    )
    with pytest.raises(AppError) as exc_info:
        await provider.discover_businesses(pune_search_spec)
    assert exc_info.value.code == "DISCOVERY_PROVIDER_TIMEOUT"
    assert exc_info.value.status_code == 504


@pytest.mark.anyio
async def test_overture_duckdb_adapter_with_local_parquet_fixture(
    pune_search_spec: SearchSpecification,
):
    fixture_path = Path("D:/Prospectra/tests/data/sample_places.parquet").as_posix()
    assert Path(fixture_path).exists()

    provider = OvertureDuckDBDiscoveryProvider(parquet_path_override=fixture_path)
    candidates = await provider.discover_businesses(pune_search_spec)

    # From sample_places.parquet:
    # place_001: Blue Tokai (cafe/coffee_shop, Pune) -> matches
    # place_002: German Bakery (bakery/bakery, Pune) -> matches
    # place_003: Vaishali (restaurant, Pune) -> excluded by category filter (pune_search_spec only has cafe, bakery)
    # place_004: Distant Mumbai Cafe (lat 19.07, lon 72.87) -> excluded by Pune bounding box filter
    assert len(candidates) == 2
    names = {c.name for c in candidates}
    assert "Blue Tokai Coffee Roasters" in names
    assert "German Bakery" in names
    assert "Vaishali Restaurant" not in names
    assert "Distant Mumbai Cafe" not in names


@pytest.mark.anyio
async def test_overture_duckdb_adapter_dynamic_stac_resolution():
    provider = OvertureDuckDBDiscoveryProvider(
        stac_url="https://stac.overturemaps.org/catalog.json"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "links": [
            {"rel": "child", "href": "https://stac.overturemaps.org/2026-08-20.0/catalog.json"},
            {"rel": "child", "href": "https://stac.overturemaps.org/2026-09-23.1/catalog.json"},
            {"rel": "self", "href": "https://stac.overturemaps.org/catalog.json"},
        ]
    }

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        release = await provider.get_latest_release()
        assert release == "2026-09-23.1"


def test_discovery_provider_factory(test_settings: Settings):
    test_settings.DISCOVERY_PROVIDER = "mock"
    mock_p = get_discovery_provider(test_settings)
    assert isinstance(mock_p, MockDiscoveryProvider)

    test_settings.DISCOVERY_PROVIDER = "overture"
    overture_p = get_discovery_provider(test_settings)
    assert isinstance(overture_p, OvertureDuckDBDiscoveryProvider)

    test_settings.DISCOVERY_PROVIDER = "invalid"
    with pytest.raises(ValueError):
        get_discovery_provider(test_settings)
