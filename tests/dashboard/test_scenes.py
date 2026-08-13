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


async def test_idle_scene_with_weather_entity(hass):
    hass.states.async_set("weather.home", "sunny", {"temperature": 21.5, "temperature_unit": "°C"})

    result = await scenes.async_render_idle_scene(hass, "weather.home", 556, 512)

    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)


async def test_idle_scene_missing_entity_still_renders(hass):
    result = await scenes.async_render_idle_scene(hass, "weather.does_not_exist", 556, 512)

    assert result.startswith(PNG_MAGIC)


async def test_get_weather_forecast_returns_empty_when_service_unavailable(hass):
    # weather.get_forecasts isn't registered by the test weather entity fixture used here.
    forecast = await scenes.async_get_weather_forecast(hass, "weather.home")

    assert forecast == []


async def test_media_scene_returns_none_when_not_playing(hass):
    hass.states.async_set("media_player.appletv", "paused", {"entity_picture": "/img.png"})
    hass.states.async_set("weather.home", "sunny", {"temperature": 21.5, "temperature_unit": "°C"})

    result = await scenes.async_render_media_scene(hass, "media_player.appletv", "weather.home", 556, 512)

    assert result is None


async def test_media_scene_renders_with_artwork(hass):
    hass.states.async_set(
        "media_player.appletv",
        "playing",
        {"entity_picture": "http://example.local/art.png", "media_title": "Some Movie"},
    )
    hass.states.async_set("weather.home", "sunny", {"temperature": 21.5, "temperature_unit": "°C"})
    artwork = _make_png_bytes()

    with patch("custom_components.minitel_interface.dashboard.scenes.async_get_clientsession") as mock_session:
        mock_session.return_value = _FakeSession(artwork)
        result = await scenes.async_render_media_scene(hass, "media_player.appletv", "weather.home", 556, 512)

    assert result is not None
    assert result.startswith(PNG_MAGIC)


async def test_media_scene_falls_back_to_logo_when_no_artwork(hass, tmp_path):
    logo_dir = tmp_path / "logos"
    logo_dir.mkdir()
    (logo_dir / "netflix.png").write_bytes(_make_png_bytes())

    hass.states.async_set(
        "media_player.appletv",
        "playing",
        {"app_name": "Netflix", "media_title": "Some Movie"},
    )
    hass.states.async_set("weather.home", "sunny", {"temperature": 21.5, "temperature_unit": "°C"})
    hass.config.allowlist_external_dirs = {str(logo_dir)}

    result = await scenes.async_render_media_scene(
        hass, "media_player.appletv", "weather.home", 556, 512, logo_dir=str(logo_dir)
    )

    assert result is not None
    assert result.startswith(PNG_MAGIC)


async def test_resolve_media_thumbnail_none_when_no_artwork_and_no_logo_dir(hass):
    hass.states.async_set("media_player.appletv", "playing", {"media_title": "Some Movie"})

    result = await scenes.async_resolve_media_thumbnail(hass, "media_player.appletv", None)

    assert result is None
