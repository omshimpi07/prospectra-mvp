"""SSRF defense and IP range validation."""

import ipaddress
import socket
from urllib.parse import urlparse

from backend.middleware.errors import AppError

BLOCKED_NETWORKS = [
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.88.99.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("2001:db8::/32"),
]

BLOCKED_EXACT_IPS = {
    "169.254.169.254",  # Cloud metadata (AWS, GCP, Azure, DO)
    "100.100.100.200",  # Alibaba Cloud metadata
    "fd00:ec2::254",  # AWS IPv6 IMDS
}


def validate_ip_address(ip_str: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """Validate that an IP address is a public, non-reserved, non-cloud-metadata address.

    Raises AppError(code='SSRF_VIOLATION') if the IP is blocked.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError as err:
        raise AppError(
            "INVALID_IP_FORMAT", f"Invalid IP address format: {ip_str}", status_code=400
        ) from err

    if ip_str in BLOCKED_EXACT_IPS:
        raise AppError(
            "SSRF_VIOLATION", f"Target IP {ip_str} is a blocked metadata service.", status_code=400
        )

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise AppError(
            "SSRF_VIOLATION",
            f"Target IP {ip_str} is in a private or reserved range.",
            status_code=400,
        )

    for net in BLOCKED_NETWORKS:
        if ip in net:
            raise AppError(
                "SSRF_VIOLATION",
                f"Target IP {ip_str} belongs to blocked subnet {net}.",
                status_code=400,
            )

    return ip


def resolve_and_validate_hostname(hostname: str) -> list[str]:
    """Resolve a hostname via DNS and validate that all returned IPs are safe public addresses.

    Raises AppError(code='SSRF_VIOLATION') if any IP is private/reserved/cloud-metadata.
    Raises AppError(code='DNS_RESOLUTION_FAILED') if hostname cannot be resolved.
    """
    clean_host = hostname.strip().lower().rstrip(".")
    if not clean_host:
        raise AppError("INVALID_HOST", "Hostname cannot be empty.", status_code=400)

    # Check if host is already an IP address
    try:
        validate_ip_address(clean_host)
        return [clean_host]
    except AppError as e:
        if e.code == "SSRF_VIOLATION":
            raise
        # Not a raw IP, proceed to DNS resolution

    try:
        addrinfo = socket.getaddrinfo(
            clean_host, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
    except socket.gaierror as err:
        raise AppError(
            "DNS_RESOLUTION_FAILED",
            f"Could not resolve host '{clean_host}': {err}",
            status_code=400,
        ) from err

    resolved_ips: set[str] = set()
    for entry in addrinfo:
        sockaddr = entry[4]
        ip_str = str(sockaddr[0])
        # Validate every resolved IP
        validate_ip_address(ip_str)
        resolved_ips.add(ip_str)

    if not resolved_ips:
        raise AppError(
            "DNS_RESOLUTION_FAILED",
            f"No IP addresses resolved for host '{clean_host}'.",
            status_code=400,
        )

    return sorted(resolved_ips)


def validate_url(url: str) -> tuple[str, str, int]:
    """Validate URL syntax, scheme, and extract (scheme, hostname, port)."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise AppError(
            "UNSUPPORTED_SCHEME",
            f"URL scheme '{scheme}' is not allowed. Only HTTP and HTTPS are permitted.",
            status_code=400,
        )

    hostname = parsed.hostname
    if not hostname:
        raise AppError("INVALID_URL", "URL does not contain a valid hostname.", status_code=400)

    port = parsed.port or (443 if scheme == "https" else 80)
    return scheme, hostname, port
