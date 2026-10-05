"""Discovery providers package."""

from backend.providers.discovery.base import DiscoveredCandidate, DiscoveryProvider
from backend.providers.discovery.factory import get_discovery_provider
from backend.providers.discovery.mock import MockDiscoveryProvider
from backend.providers.discovery.overture import OvertureDuckDBDiscoveryProvider

__all__ = [
    "DiscoveredCandidate",
    "DiscoveryProvider",
    "get_discovery_provider",
    "MockDiscoveryProvider",
    "OvertureDuckDBDiscoveryProvider",
]
