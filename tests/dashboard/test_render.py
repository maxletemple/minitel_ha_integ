"""Direct tests for dashboard.render (no Home Assistant fixtures needed)."""

from io import BytesIO

from PIL import Image
import pytest

from custom_components.minitel_interface.dashboard.render import render_idle_scene, render_media_scene

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_png_bytes(size=(50, 50), color=128) -> bytes:
    buf = BytesIO()
    Image.new("L", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_render_idle_scene_returns_valid_png():
    result = render_idle_scene(
        556, 512, clock_text="12:34", condition_text="Ensoleille", temperature_text="21.5C"
    )
    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)
    assert image.mode == "L"


def test_render_idle_scene_with_forecast():
    forecast = [
        ("Mon", "sunny", "22C", "12C"),
        ("Tue", "cloudy", "20C", "11C"),
        ("Wed", "rainy", "18C", "10C"),
        ("Thu", "sunny", "23C", "13C"),
        ("Fri", "windy", "19C", "9C"),
    ]
    result = render_idle_scene(
        556, 512, clock_text="12:34", condition_text="sunny", temperature_text="21.5C", forecast=forecast
    )
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)


def test_render_idle_scene_respects_background_color():
    result = render_idle_scene(
        200, 200, clock_text="", condition_text="", temperature_text="", background_color=200
    )
    image = Image.open(BytesIO(result))
    assert image.getpixel((199, 5)) == 200


def test_render_media_scene_without_thumbnail():
    result = render_media_scene(
        556, 512, clock_text="12:34", condition_text="sunny", temperature_text="21C", title_text="Some Movie"
    )
    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)


def test_render_media_scene_with_thumbnail():
    thumbnail = _make_png_bytes()
    result = render_media_scene(
        556,
        512,
        clock_text="12:34",
        condition_text="sunny",
        temperature_text="21C",
        title_text="Some Movie",
        thumbnail_bytes=thumbnail,
    )
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)


def test_render_media_scene_invalid_thumbnail_raises():
    with pytest.raises(ValueError):
        render_media_scene(
            556,
            512,
            clock_text="12:34",
            condition_text="sunny",
            temperature_text="21C",
            title_text="Some Movie",
            thumbnail_bytes=b"not an image",
        )
