"""Tests for WmClient against an in-memory fake TCP wm-server."""

from __future__ import annotations

import asyncio
import struct

import pytest

from custom_components.minitel_interface.wmclient import WmClient
from custom_components.minitel_interface.wmclient.const import CMD_GET_SUMMARY, CMD_WIN_CREATE


class FakeWmServer:
    """Minimal fake wm-server: records received packets, answers CMD_GET_SUMMARY."""

    def __init__(self) -> None:
        self.received: list[tuple[int, int, int, bytes]] = []
        self._server: asyncio.AbstractServer | None = None
        self.summary_response = struct.pack("<H", 0)  # 0 windows

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._handle_client, "127.0.0.1", 0)
        return self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                header = await reader.readexactly(8)
                size, command, flags, data_type = struct.unpack("<IBHB", header)
                payload = await reader.readexactly(size) if size else b""
                self.received.append((command, flags, data_type, payload))

                if command == CMD_GET_SUMMARY:
                    response_header = struct.pack("<IBHB", len(self.summary_response), CMD_GET_SUMMARY, 0, 0)
                    writer.write(response_header + self.summary_response)
                    await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()


@pytest.fixture
async def fake_server(socket_enabled):
    server = FakeWmServer()
    port = await server.start()
    yield server, port
    await server.stop()


async def test_win_create_sends_expected_bytes(fake_server):
    server, port = fake_server
    client = WmClient("127.0.0.1", port)
    await client.async_connect()
    try:
        await client.async_win_create(10, 20, 100, 200, 5)
        await asyncio.sleep(0.05)
    finally:
        await client.async_close()

    assert len(server.received) == 1
    command, flags, data_type, payload = server.received[0]
    assert command == CMD_WIN_CREATE
    assert flags == 0
    assert data_type == 0
    assert payload == struct.pack("<HHHHB", 10, 20, 100, 200, 5)


async def test_get_summary_round_trip(fake_server):
    server, port = fake_server
    win_summary = struct.pack("<HHHHBH", 0, 0, 556, 512, 0, 0)
    server.summary_response = struct.pack("<H", 1) + win_summary

    client = WmClient("127.0.0.1", port)
    await client.async_connect()
    try:
        windows = await client.async_get_summary()
    finally:
        await client.async_close()

    assert len(windows) == 1
    assert (windows[0].width, windows[0].height) == (556, 512)


async def test_commands_are_serialized(fake_server):
    """Concurrent calls must never interleave bytes on the wire."""
    server, port = fake_server
    client = WmClient("127.0.0.1", port)
    await client.async_connect()
    try:
        await asyncio.gather(
            *(client.async_win_create(i, i, 10, 10, 0) for i in range(20))
        )
        await asyncio.sleep(0.05)
    finally:
        await client.async_close()

    assert len(server.received) == 20
    seen = {struct.unpack("<HHHHB", payload)[0] for _, _, _, payload in server.received}
    assert seen == set(range(20))
