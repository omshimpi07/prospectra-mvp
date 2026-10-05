"""Connection-pinning network backend and transport for DNS rebinding defense."""

from typing import Any

import httpcore
import httpx


class PinnedAsyncNetworkBackend(httpcore.AnyIOBackend):
    """Network backend that overrides TCP destination IP with a pre-validated pinned IP.

    This prevents TOCTOU (Time-of-Check to Time-of-Use) DNS rebinding attacks:
    the socket connects strictly to the pre-validated IP address, while the original
    hostname is preserved for TLS SNI extension and HTTP Host header verification.
    """

    def __init__(self, host_to_ip: dict[str, str]) -> None:
        super().__init__()
        self.host_to_ip = host_to_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        pinned_ip = self.host_to_ip.get(host, host)
        return await super().connect_tcp(
            pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """Async HTTP transport enforcing pinned IP connection for DNS rebinding protection."""

    def __init__(self, host_to_ip: dict[str, str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pool = httpcore.AsyncConnectionPool(
            network_backend=PinnedAsyncNetworkBackend(host_to_ip),
            ssl_context=self._pool._ssl_context,
            http1=self._pool._http1,
            http2=self._pool._http2,
            retries=self._pool._retries,
        )
