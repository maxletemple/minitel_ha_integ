"""Persistent single-client TCP connection to wm-server.

wm-server accepts only one client at a time and has no request/response
correlation id. This module therefore serializes every exchange (write, and
read when applicable) behind a single lock, and never has more than one
request in flight.
"""

from __future__ import annotations

import asyncio

from .exceptions import WmConnectionError, WmTimeoutError

_CONNECT_TIMEOUT = 5.0
_READ_TIMEOUT = 5.0


class WmConnection:
    """Manages a single persistent TCP connection to wm-server."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def async_connect(self) -> None:
        """Open the TCP connection. Raises WmConnectionError on failure."""
        try:
            async with asyncio.timeout(_CONNECT_TIMEOUT):
                self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        except (OSError, asyncio.TimeoutError) as err:
            raise WmConnectionError(f"cannot connect to {self._host}:{self._port}: {err}") from err

    async def async_close(self) -> None:
        """Close the TCP connection."""
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = None
        self._writer = None

    async def async_send(self, data: bytes) -> None:
        """Send raw bytes, reconnecting once on failure. Must be called under the lock."""
        if not self.connected:
            await self.async_connect()
        assert self._writer is not None
        try:
            self._writer.write(data)
            await self._writer.drain()
        except (OSError, ConnectionError) as err:
            await self.async_close()
            raise WmConnectionError(f"failed to send data to {self._host}:{self._port}: {err}") from err

    async def async_read_exact(self, n: int) -> bytes:
        """Read exactly n bytes. Must be called under the lock."""
        if self._reader is None:
            raise WmConnectionError("not connected")
        try:
            async with asyncio.timeout(_READ_TIMEOUT):
                return await self._reader.readexactly(n)
        except asyncio.IncompleteReadError as err:
            await self.async_close()
            raise WmConnectionError("connection closed while reading response") from err
        except asyncio.TimeoutError as err:
            await self.async_close()
            raise WmTimeoutError(f"no response from {self._host}:{self._port} within {_READ_TIMEOUT}s") from err

    def lock(self) -> asyncio.Lock:
        """Lock guarding a full request/response exchange."""
        return self._lock
