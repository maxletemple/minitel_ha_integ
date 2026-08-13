"""Tests for dashboard.scenes against a real (test) HA state machine."""

from io import BytesIO
from unittest.mock import patch

from PIL import Image
import pytest

from custom_components.minitel_interface.dashboard import scenes

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_png_bytes(size=(20, 20), color=128) -> bytes:
    buf = BytesIO()
    Image.new("L", size, color).save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    async def read(self):
        return self._data


class _FakeSession:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get(self, url):
        return _FakeResponse(self._data)


async def test_clock_weather_scene_with_weather_entity(hass):
    hass.states.async_set("weather.home", "sunny", {"temperature": 21.5, "temperature_unit": "°C"})

    result = await scenes.async_render_clock_weather_scene(hass, "weather.home", 200, 100)

    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (200, 100)


async def test_clock_weather_scene_missing_entity_still_renders(hass):
    result = await scenes.async_render_clock_weather_scene(hass, "weather.does_not_exist", 200, 100)

    assert result.startswith(PNG_MAGIC)


async def test_media_art_scene_returns_none_when_not_playing(hass):
    hass.states.async_set("media_player.appletv", "paused", {"entity_picture": "/img.png"})

    result = await scenes.async_render_media_art_scene(hass, "media_player.appletv", 200, 100)

    assert result is None


async def test_media_art_scene_returns_none_without_picture(hass):
    hass.states.async_set("media_player.appletv", "playing", {})

    result = await scenes.async_render_media_art_scene(hass, "media_player.appletv", 200, 100)

    assert result is None


async def test_media_art_scene_renders_when_playing(hass):
    hass.states.async_set(
        "media_player.appletv",
        "playing",
        {"entity_picture": "http://example.local/art.png", "media_title": "Some Movie"},
    )
    artwork = _make_png_bytes()

    with patch("custom_components.minitel_interface.dashboard.scenes.async_get_clientsession") as mock_session:
        mock_session.return_value = _FakeSession(artwork)
        result = await scenes.async_render_media_art_scene(hass, "media_player.appletv", 200, 100)

    assert result is not None
    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (200, 100)


async def test_media_art_scene_falls_back_on_invalid_artwork(hass):
    hass.states.async_set(
        "media_player.appletv",
        "playing",
        {"entity_picture": "http://example.local/art.png", "media_title": "Some Movie"},
    )

    with patch("custom_components.minitel_interface.dashboard.scenes.async_get_clientsession") as mock_session:
        mock_session.return_value = _FakeSession(b"not an image")
        result = await scenes.async_render_media_art_scene(hass, "media_player.appletv", 200, 100)

    assert result is None
