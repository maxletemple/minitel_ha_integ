"""Data models for wm-server state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectSummary:
    """A display object inside a window, as reported by CMD_GET_SUMMARY."""

    index: int
    data_type: int


@dataclass(frozen=True)
class WinSummary:
    """A window, as reported by CMD_GET_SUMMARY."""

    index: int
    pos_x: int
    pos_y: int
    width: int
    height: int
    background_color: int
    objects: tuple[ObjectSummary, ...]
