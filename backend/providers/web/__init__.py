"""Web intelligence, SSRF defense, and signal extraction package."""

from backend.providers.web.extractors import extract_signals_from_page
from backend.providers.web.fetcher import FetchedPage, SecureWebFetcher
from backend.providers.web.pinning import PinnedAsyncHTTPTransport, PinnedAsyncNetworkBackend
from backend.providers.web.ssrf import (
    resolve_and_validate_hostname,
    validate_ip_address,
    validate_url,
)

__all__ = [
    "SecureWebFetcher",
    "FetchedPage",
    "extract_signals_from_page",
    "resolve_and_validate_hostname",
    "validate_ip_address",
    "validate_url",
    "PinnedAsyncHTTPTransport",
    "PinnedAsyncNetworkBackend",
]
