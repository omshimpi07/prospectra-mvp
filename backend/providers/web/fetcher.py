"""SSRF-safe, connection-pinned web fetcher."""

import asyncio
from dataclasses import dataclass, field
import datetime
import logging
import socket
import ssl
import time
from urllib.parse import urljoin

import httpx

from backend.config import Settings, get_settings
from backend.middleware.errors import AppError
from backend.providers.web.pinning import PinnedAsyncHTTPTransport
from backend.providers.web.ssrf import (
    resolve_and_validate_hostname,
    validate_url,
)

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "ProspectraBot/1.0 (+https://prospectra.ai/bot; bot@prospectra.ai)"


@dataclass
class FetchedPage:
    """Result of fetching an external webpage with security and health metadata."""

    original_url: str
    final_url: str
    status_code: int | None = None
    reachable: bool = False
    headers: dict[str, str] = field(default_factory=dict)
    content_bytes: bytes = b""
    text: str = ""
    response_time_ms: float = 0.0
    https_enforced: bool = False
    ssl_valid: bool | None = None
    ssl_days_remaining: int | None = None
    redirect_chain: list[str] = field(default_factory=list)
    ip_address: str | None = None
    dns_resolves: bool | None = None
    error: str | None = None


def check_ssl_certificate(
    hostname: str, pinned_ip: str, port: int = 443, timeout: float = 5.0
) -> tuple[bool, int | None]:
    """Inspect SSL/TLS certificate validity and expiration using pinned IP."""
    context = ssl.create_default_context()
    try:
        with socket.create_connection((pinned_ip, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if not cert or "notAfter" not in cert:
                    return True, None
                not_after_str = str(cert["notAfter"])
                # OpenSSL format e.g.: 'May 15 12:00:00 2026 GMT'
                expire_date = datetime.datetime.strptime(
                    not_after_str, "%b %d %H:%M:%S %Y %Z"
                ).replace(tzinfo=datetime.timezone.utc)
                now = datetime.datetime.now(datetime.timezone.utc)
                days_remaining = (expire_date - now).days
                return True, max(0, days_remaining)
    except Exception as exc:
        logger.debug("SSL check failed for %s (%s): %s", hostname, pinned_ip, exc)
        return False, None


class SecureWebFetcher:
    """Async web fetcher enforcing strict SSRF defense and DNS rebinding prevention."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.timeout = self.settings.WEB_FETCH_TIMEOUT_SECONDS
        self.connect_timeout = self.settings.WEB_CONNECT_TIMEOUT_SECONDS
        self.max_bytes = self.settings.WEB_MAX_RESPONSE_BYTES
        self.max_redirects = self.settings.WEB_MAX_REDIRECTS

    async def fetch(self, raw_url: str) -> FetchedPage:
        """Fetch a website with DNS validation, connection pinning, and response bounding."""
        url = raw_url.strip()
        if not url:
            return FetchedPage(
                original_url=raw_url,
                final_url=raw_url,
                reachable=False,
                error="EMPTY_URL",
            )

        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"

        original_url = url
        current_url = url
        redirect_chain: list[str] = []
        last_ip: str | None = None

        for redirect_count in range(self.max_redirects + 1):
            try:
                scheme, hostname, port = validate_url(current_url)
            except AppError as e:
                return FetchedPage(
                    original_url=original_url,
                    final_url=current_url,
                    reachable=False,
                    redirect_chain=redirect_chain,
                    error=e.code,
                )

            # DNS resolution and SSRF validation
            try:
                resolved_ips = resolve_and_validate_hostname(hostname)
            except AppError as e:
                return FetchedPage(
                    original_url=original_url,
                    final_url=current_url,
                    reachable=False,
                    redirect_chain=redirect_chain,
                    dns_resolves=False if e.code == "DNS_RESOLUTION_FAILED" else None,
                    error=e.code,
                )

            pinned_ip = resolved_ips[0]
            last_ip = pinned_ip

            # Connection-pinning transport
            transport = PinnedAsyncHTTPTransport({hostname: pinned_ip})
            timeout_cfg = httpx.Timeout(self.timeout, connect=self.connect_timeout)

            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(
                    transport=transport,
                    follow_redirects=False,
                    timeout=timeout_cfg,
                    verify=True,
                ) as client:
                    headers = {
                        "User-Agent": DEFAULT_USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
                    }
                    resp = await client.get(current_url, headers=headers)
                    t1 = time.perf_counter()
                    response_time_ms = round((t1 - t0) * 1000.0, 2)

                    # Handle Redirects
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("Location")
                        if not location:
                            break
                        redirect_chain.append(current_url)
                        current_url = urljoin(current_url, location)
                        continue

                    # Terminal response
                    content_bytes = resp.content[: self.max_bytes]
                    try:
                        text = content_bytes.decode(resp.encoding or "utf-8", errors="replace")
                    except Exception:
                        text = content_bytes.decode("utf-8", errors="replace")

                    https_enforced = current_url.startswith("https://")
                    ssl_valid: bool | None = None
                    ssl_days_remaining: int | None = None

                    if https_enforced:
                        ssl_valid, ssl_days_remaining = await asyncio.to_thread(
                            check_ssl_certificate, hostname, pinned_ip, port, self.connect_timeout
                        )

                    return FetchedPage(
                        original_url=original_url,
                        final_url=current_url,
                        status_code=resp.status_code,
                        reachable=200 <= resp.status_code < 400,
                        headers=dict(resp.headers),
                        content_bytes=content_bytes,
                        text=text,
                        response_time_ms=response_time_ms,
                        https_enforced=https_enforced,
                        ssl_valid=ssl_valid,
                        ssl_days_remaining=ssl_days_remaining,
                        redirect_chain=redirect_chain,
                        ip_address=last_ip,
                        dns_resolves=True,
                        error=None,
                    )

            except httpx.ConnectTimeout:
                return FetchedPage(
                    original_url=original_url,
                    final_url=current_url,
                    reachable=False,
                    redirect_chain=redirect_chain,
                    ip_address=last_ip,
                    dns_resolves=True,
                    error="CONNECT_TIMEOUT",
                )
            except (httpx.ConnectError, httpx.RequestError) as exc:
                return FetchedPage(
                    original_url=original_url,
                    final_url=current_url,
                    reachable=False,
                    redirect_chain=redirect_chain,
                    ip_address=last_ip,
                    dns_resolves=True,
                    error=f"NETWORK_ERROR: {type(exc).__name__}",
                )

        return FetchedPage(
            original_url=original_url,
            final_url=current_url,
            reachable=False,
            redirect_chain=redirect_chain,
            ip_address=last_ip,
            dns_resolves=True,
            error="TOO_MANY_REDIRECTS",
        )
