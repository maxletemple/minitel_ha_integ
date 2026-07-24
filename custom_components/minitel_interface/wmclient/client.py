"""High-level async client for wm-server."""

from __future__ import annotations

from . import protocol
from .connection import WmConnection
from .const import (
    CMD_GET_SUMMARY,
    CMD_PING,
    CMD_RM_OBJECT,
    CMD_SET_OBJECT,
    CMD_WIN_CREATE,
    CMD_WIN_DESTROY,
    CMD_WIN_ORDER,
    CMD_WIN_TRANSFORM,
    DEFAULT_PORT,
    FLAG_FULLSCREEN,
    PFMT_JPEG,
    PFMT_PNG,
    VFMT_H264,
)
from .models import WinSummary


class WmClient:
    """Async client exposing one method per wm-server command.

    wm-server accepts a single client at a time and has no request id, so
    every call is serialized behind the connection's lock: at most one
    command is ever in flight.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self._connection = WmConnection(host, port)

    @property
    def connected(self) -> bool:
        return self._connection.connected

    async def async_connect(self) -> None:
        await self._connection.async_connect()

    async def async_close(self) -> None:
        await self._connection.async_close()

    async def _async_send_command(self, command: int, payload: bytes, *, flags: int = 0, data_type: int = 0) -> None:
        header = protocol.encode_header(command, len(payload), flags=flags, data_type=data_type)
        async with self._connection.lock():
            await self._connection.async_send(header + payload)

    async def async_ping(self) -> None:
        await self._async_send_command(CMD_PING, b"")

    async def async_win_create(self, pos_x: int, pos_y: int, width: int, height: int, background_color: int = 0) -> None:
        payload = protocol.encode_win_create(pos_x, pos_y, width, height, background_color)
        await self._async_send_command(CMD_WIN_CREATE, payload)

    async def async_win_destroy(self, win_index: int) -> None:
        payload = protocol.encode_win_destroy(win_index)
        await self._async_send_command(CMD_WIN_DESTROY, payload)

    async def async_win_transform(self, win_index: int, pos_x: int, pos_y: int, width: int, height: int) -> None:
        payload = protocol.encode_win_transform(win_index, pos_x, pos_y, width, height)
        await self._async_send_command(CMD_WIN_TRANSFORM, payload)

    async def async_win_order(self, win_index: int, order: int) -> None:
        payload = protocol.encode_win_order(win_index, order)
        await self._async_send_command(CMD_WIN_ORDER, payload)

    async def async_rm_object(self, win_index: int, obj_index: int) -> None:
        payload = protocol.encode_rm_object(win_index, obj_index)
        await self._async_send_command(CMD_RM_OBJECT, payload)

    async def async_set_object_text(
        self, win_index: int, obj_index: int, x: int, y: int, width: int, height: int, font_size: int, text: str
    ) -> None:
        payload, data_type = protocol.encode_set_text(win_index, obj_index, x, y, width, height, font_size, text)
        await self._async_send_command(CMD_SET_OBJECT, payload, data_type=data_type)

    async def async_set_object_picture(
        self,
        win_index: int,
        obj_index: int,
        x: int,
        y: int,
        width: int,
        height: int,
        image_bytes: bytes,
        *,
        is_png: bool = False,
    ) -> None:
        fmt = PFMT_PNG if is_png else PFMT_JPEG
        payload, data_type = protocol.encode_set_picture(win_index, obj_index, x, y, width, height, fmt, image_bytes)
        await self._async_send_command(CMD_SET_OBJECT, payload, data_type=data_type)

    async def async_set_object_video(
        self,
        win_index: int,
        obj_index: int,
        x: int,
        y: int,
        width: int,
        height: int,
        video_bytes: bytes,
        *,
        fullscreen: bool = False,
    ) -> None:
        payload, data_type = protocol.encode_set_video(
            win_index, obj_index, x, y, width, height, VFMT_H264, video_bytes
        )
        flags = FLAG_FULLSCREEN if fullscreen else 0
        await self._async_send_command(CMD_SET_OBJECT, payload, flags=flags, data_type=data_type)

    async def async_get_summary(self) -> list[WinSummary]:
        header = protocol.encode_header(CMD_GET_SUMMARY, 0)
        async with self._connection.lock():
            await self._connection.async_send(header)
            response_header = await self._connection.async_read_exact(protocol.HEADER.size)
            size, _command, _flags, _data_type = protocol.decode_header(response_header)
            payload = await self._connection.async_read_exact(size) if size else b""
        return protocol.decode_summary(payload)
