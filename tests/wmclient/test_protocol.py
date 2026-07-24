"""Byte-exact round-trip tests for wmclient.protocol.

Expected payloads are cross-checked against light-wm/send_packet.py, the
reference client used against the real wm-server.
"""

import struct

from custom_components.minitel_interface.wmclient import protocol
from custom_components.minitel_interface.wmclient.const import (
    DTYPE_PICTURE,
    DTYPE_TEXT,
    DTYPE_VIDEO,
    PFMT_JPEG,
    PFMT_PNG,
    VFMT_H264,
)


def test_encode_header():
    assert protocol.encode_header(0x5, 10, flags=0x0001, data_type=0x2) == struct.pack("<IBHB", 10, 0x5, 0x0001, 0x2)


def test_decode_header_round_trip():
    header = protocol.encode_header(0x7, 0)
    assert protocol.decode_header(header) == (0, 0x7, 0, 0)


def test_encode_win_create():
    assert protocol.encode_win_create(10, 20, 100, 200, 5) == struct.pack("<HHHHB", 10, 20, 100, 200, 5)


def test_encode_win_destroy():
    assert protocol.encode_win_destroy(3) == struct.pack("<H", 3)


def test_encode_win_transform():
    assert protocol.encode_win_transform(1, 0, 0, 50, 60) == struct.pack("<HHHHH", 1, 0, 0, 50, 60)


def test_encode_win_order():
    assert protocol.encode_win_order(2, 1) == struct.pack("<HH", 2, 1)


def test_encode_rm_object():
    assert protocol.encode_rm_object(1, 0) == struct.pack("<HH", 1, 0)


def test_encode_set_text():
    payload, data_type = protocol.encode_set_text(0, 0, 0, 0, 100, 20, 8, "hello")
    expected = struct.pack("<HHHHHH", 0, 0, 0, 0, 100, 20) + struct.pack("<H", 8) + b"hello\x00"
    assert payload == expected
    assert data_type == DTYPE_TEXT


def test_encode_set_picture():
    payload, data_type = protocol.encode_set_picture(0, 0, 0, 0, 556, 512, PFMT_JPEG, b"\xff\xd8\xff")
    expected = struct.pack("<HHHHHH", 0, 0, 0, 0, 556, 512) + struct.pack("<B", PFMT_JPEG) + b"\xff\xd8\xff"
    assert payload == expected
    assert data_type == DTYPE_PICTURE


def test_encode_set_picture_png():
    payload, _ = protocol.encode_set_picture(0, 0, 0, 0, 10, 10, PFMT_PNG, b"\x89PNG")
    assert payload[12:13] == struct.pack("<B", PFMT_PNG)


def test_encode_set_video():
    payload, data_type = protocol.encode_set_video(0, 0, 0, 0, 320, 240, VFMT_H264, b"\x00\x00\x00\x01")
    expected = struct.pack("<HHHHHH", 0, 0, 0, 0, 320, 240) + struct.pack("<B", VFMT_H264) + b"\x00\x00\x00\x01"
    assert payload == expected
    assert data_type == DTYPE_VIDEO


def test_decode_summary_empty():
    payload = struct.pack("<H", 0)
    assert protocol.decode_summary(payload) == []


def test_decode_summary_round_trip():
    win_summary = struct.pack("<HHHHBH", 0, 0, 556, 512, 0, 2)
    obj_types = struct.pack("<B", DTYPE_TEXT) + struct.pack("<B", DTYPE_PICTURE)
    payload = struct.pack("<H", 1) + win_summary + obj_types

    windows = protocol.decode_summary(payload)

    assert len(windows) == 1
    win = windows[0]
    assert (win.index, win.pos_x, win.pos_y, win.width, win.height, win.background_color) == (0, 0, 0, 556, 512, 0)
    assert [o.data_type for o in win.objects] == [DTYPE_TEXT, DTYPE_PICTURE]
