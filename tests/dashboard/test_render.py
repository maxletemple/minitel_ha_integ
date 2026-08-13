"""Direct tests for dashboard.render (no Home Assistant fixtures needed)."""

from io import BytesIO

from PIL import Image
import pytest

from custom_components.minitel_interface.dashboard.render import (
    compose_media_art,
    render_clock_weather,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_png_bytes(size=(20, 20), color=128) -> bytes:
    buf = BytesIO()
    Image.new("L", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_render_clock_weather_returns_valid_png():
    result = render_clock_weather(
        200, 100, clock_text="12:34", condition_text="Ensoleille", temperature_text="21.5C"
    )
    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (200, 100)
    assert image.mode == "L"


def test_render_clock_weather_respects_background_color():
    result = render_clock_weather(
        200, 100, clock_text="12:34", condition_text="", temperature_text="", background_color=200
    )
    image = Image.open(BytesIO(result))
    # Bottom-right corner is far from any drawn text.
    assert image.getpixel((199, 99)) == 200


def test_compose_media_art_returns_valid_png():
    artwork = _make_png_bytes(size=(50, 50))
    result = compose_media_art(200, 100, artwork, "Some Title")
    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (200, 100)
    assert image.mode == "L"


def test_compose_media_art_invalid_bytes_raises():
    with pytest.raises(ValueError):
        compose_media_art(200, 100, b"not an image", "Some Title")
