"""Binary (de)serialization for the wm-server wire protocol.

All structs are little-endian and packed (no padding), matching the C++
server's `#pragma pack`-style layout described in PROTOCOL.md and verified
against light-wm/include/structs.h and light-wm/send_packet.py.
"""

from __future__ import annotations

import struct

from .const import DTYPE_PICTURE, DTYPE_TEXT, DTYPE_VIDEO
from .exceptions import WmProtocolError
from .models import ObjectSummary, WinSummary

HEADER = struct.Struct("<IBHB")  # size, command, flags, data_type

_WIN_CREATE = struct.Struct("<HHHHB")  # posX, posY, width, height, backgroundColor
_WIN_DESTROY = struct.Struct("<H")  # winIndex
_WIN_TRANSFORM = struct.Struct("<HHHHH")  # winIndex, posX, posY, width, height
_WIN_ORDER = struct.Struct("<HH")  # winIndex, order
_OBJ_SET = struct.Struct("<HHHHHH")  # winIndex, objIndex, x, y, width, height
_OBJ_REMOVE = struct.Struct("<HH")  # winIndex, objIndex
_TEXT_HEADER = struct.Struct("<H")  # fontSize
_PICTURE_HEADER = struct.Struct("<B")  # format
_VIDEO_HEADER = struct.Struct("<B")  # format
_SUMMARY_HEADER = struct.Struct("<H")  # windowCount
_WIN_SUMMARY = struct.Struct("<HHHHBH")  # posX, posY, width, height, bgColor, objectCount
_OBJECT_TYPE = struct.Struct("<B")


def encode_header(command: int, payload_len: int, *, flags: int = 0, data_type: int = 0) -> bytes:
    """Encode a RawPacketHeader."""
    return HEADER.pack(payload_len, command, flags, data_type)


def decode_header(data: bytes) -> tuple[int, int, int, int]:
    """Decode a RawPacketHeader into (size, command, flags, data_type)."""
    if len(data) != HEADER.size:
        raise WmProtocolError(f"expected {HEADER.size} header bytes, got {len(data)}")
    return HEADER.unpack(data)


def encode_win_create(pos_x: int, pos_y: int, width: int, height: int, background_color: int) -> bytes:
    return _WIN_CREATE.pack(pos_x, pos_y, width, height, background_color)


def encode_win_destroy(win_index: int) -> bytes:
    return _WIN_DESTROY.pack(win_index)


def encode_win_transform(win_index: int, pos_x: int, pos_y: int, width: int, height: int) -> bytes:
    return _WIN_TRANSFORM.pack(win_index, pos_x, pos_y, width, height)


def encode_win_order(win_index: int, order: int) -> bytes:
    return _WIN_ORDER.pack(win_index, order)


def encode_rm_object(win_index: int, obj_index: int) -> bytes:
    return _OBJ_REMOVE.pack(win_index, obj_index)


def _encode_obj_set(win_index: int, obj_index: int, x: int, y: int, width: int, height: int) -> bytes:
    return _OBJ_SET.pack(win_index, obj_index, x, y, width, height)


def encode_set_text(
    win_index: int, obj_index: int, x: int, y: int, width: int, height: int, font_size: int, text: str
) -> tuple[bytes, int]:
    """Return (payload, data_type) for a CMD_SET_OBJECT / DTYPE_TEXT request."""
    obj_set = _encode_obj_set(win_index, obj_index, x, y, width, height)
    text_bytes = text.encode("ascii") + b"\x00"
    payload = obj_set + _TEXT_HEADER.pack(font_size) + text_bytes
    return payload, DTYPE_TEXT


def encode_set_picture(
    win_index: int, obj_index: int, x: int, y: int, width: int, height: int, fmt: int, image_bytes: bytes
) -> tuple[bytes, int]:
    """Return (payload, data_type) for a CMD_SET_OBJECT / DTYPE_PICTURE request."""
    obj_set = _encode_obj_set(win_index, obj_index, x, y, width, height)
    payload = obj_set + _PICTURE_HEADER.pack(fmt) + image_bytes
    return payload, DTYPE_PICTURE


def encode_set_video(
    win_index: int, obj_index: int, x: int, y: int, width: int, height: int, fmt: int, video_bytes: bytes
) -> tuple[bytes, int]:
    """Return (payload, data_type) for a CMD_SET_OBJECT / DTYPE_VIDEO request."""
    obj_set = _encode_obj_set(win_index, obj_index, x, y, width, height)
    payload = obj_set + _VIDEO_HEADER.pack(fmt) + video_bytes
    return payload, DTYPE_VIDEO


def decode_summary(payload: bytes) -> list[WinSummary]:
    """Decode the response payload of CMD_GET_SUMMARY."""
    offset = 0
    if len(payload) < _SUMMARY_HEADER.size:
        raise WmProtocolError("summary payload too short for header")
    (window_count,) = _SUMMARY_HEADER.unpack_from(payload, offset)
    offset += _SUMMARY_HEADER.size

    windows: list[WinSummary] = []
    for win_index in range(window_count):
        if offset + _WIN_SUMMARY.size > len(payload):
            raise WmProtocolError(f"summary payload truncated at window {win_index}")
        pos_x, pos_y, width, height, background_color, object_count = _WIN_SUMMARY.unpack_from(payload, offset)
        offset += _WIN_SUMMARY.size

        objects: list[ObjectSummary] = []
        for obj_index in range(object_count):
            if offset + _OBJECT_TYPE.size > len(payload):
                raise WmProtocolError(f"summary payload truncated at window {win_index} object {obj_index}")
            (data_type,) = _OBJECT_TYPE.unpack_from(payload, offset)
            offset += _OBJECT_TYPE.size
            objects.append(ObjectSummary(index=obj_index, data_type=data_type))

        windows.append(
            WinSummary(
                index=win_index,
                pos_x=pos_x,
                pos_y=pos_y,
                width=width,
                height=height,
                background_color=background_color,
                objects=tuple(objects),
            )
        )

    return windows
