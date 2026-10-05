"""Tests for SSRF defense, IP validation, and DNS rebinding protection."""

from unittest.mock import patch

import pytest

from backend.middleware.errors import AppError
from backend.providers.web.pinning import PinnedAsyncHTTPTransport
from backend.providers.web.ssrf import (
    resolve_and_validate_hostname,
    validate_ip_address,
    validate_url,
)


@pytest.mark.parametrize(
    "blocked_ip",
    [
        "127.0.0.1",
        "127.0.1.1",
        "10.0.0.1",
        "10.254.254.254",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "192.168.0.254",
        "169.254.169.254",  # Cloud metadata
        "100.100.100.200",  # Alibaba metadata
        "0.0.0.0",
        "::1",
        "fe80::1",
        "fd00:ec2::254",  # AWS IPv6 IMDS
    ],
)
def test_validate_ip_blocks_private_and_metadata_ips(blocked_ip: str):
    with pytest.raises(AppError) as exc_info:
        validate_ip_address(blocked_ip)
    assert exc_info.value.code == "SSRF_VIOLATION"


@pytest.mark.parametrize(
    "valid_ip",
    [
        "8.8.8.8",
        "1.1.1.1",
        "93.184.215.14",
        "2606:4700:4700::1111",
    ],
)
def test_validate_ip_allows_public_ips(valid_ip: str):
    ip = validate_ip_address(valid_ip)
    assert str(ip) == valid_ip


def test_resolve_and_validate_hostname_blocks_private_resolution():
    with patch("socket.getaddrinfo") as mock_dns:
        # Mock DNS returning a private IP
        mock_dns.return_value = [
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ]
        with pytest.raises(AppError) as exc_info:
            resolve_and_validate_hostname("internal.corp")
        assert exc_info.value.code == "SSRF_VIOLATION"


def test_resolve_and_validate_hostname_blocks_cloud_metadata():
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [
            (2, 1, 6, "", ("169.254.169.254", 0)),
        ]
        with pytest.raises(AppError) as exc_info:
            resolve_and_validate_hostname("metadata.google.internal")
        assert exc_info.value.code == "SSRF_VIOLATION"


def test_resolve_and_validate_hostname_success():
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [
            (2, 1, 6, "", ("93.184.215.14", 0)),
        ]
        ips = resolve_and_validate_hostname("example.com")
        assert ips == ["93.184.215.14"]


def test_validate_url_rejects_unsupported_schemes():
    for bad_url in [
        "file:///etc/passwd",
        "gopher://localhost:70",
        "ftp://example.com/file",
        "dict://dict.org",
        "data:text/html;base64,PHNjcmlwdD4=",
    ]:
        with pytest.raises(AppError) as exc_info:
            validate_url(bad_url)
        assert exc_info.value.code == "UNSUPPORTED_SCHEME"


def test_validate_url_success():
    scheme, host, port = validate_url("https://example.com:8443/test")
    assert scheme == "https"
    assert host == "example.com"
    assert port == 8443


@pytest.mark.anyio
async def test_dns_rebinding_pinned_transport_routes_to_pinned_ip():
    """Verify that PinnedAsyncHTTPTransport routes connection to pinned IP directly."""
    transport = PinnedAsyncHTTPTransport({"attacker.com": "93.184.215.14"})
    assert transport._pool._network_backend.host_to_ip["attacker.com"] == "93.184.215.14"
