"""Discovery Provider Factory."""

from backend.config import Settings, get_settings
from backend.providers.discovery.base import DiscoveryProvider
from backend.providers.discovery.mock import MockDiscoveryProvider
from backend.providers.discovery.overture import OvertureDuckDBDiscoveryProvider


def get_discovery_provider(settings: Settings | None = None) -> DiscoveryProvider:
    """Instantiate and return the configured DiscoveryProvider implementation."""
    cfg = settings or get_settings()

    if cfg.DISCOVERY_PROVIDER == "overture":
        return OvertureDuckDBDiscoveryProvider(
            s3_bucket=cfg.OVERTURE_S3_BUCKET,
            stac_url=cfg.OVERTURE_STAC_URL,
            pinned_release=cfg.OVERTURE_RELEASE,
            timeout_seconds=cfg.OVERTURE_QUERY_TIMEOUT_SECONDS,
        )
    if cfg.DISCOVERY_PROVIDER == "mock":
        return MockDiscoveryProvider()

    raise ValueError(f"Unsupported DISCOVERY_PROVIDER: {cfg.DISCOVERY_PROVIDER}")
