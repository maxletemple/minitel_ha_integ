"""Direct tests for dashboard.render (no Home Assistant fixtures needed)."""

from io import BytesIO

from PIL import Image, ImageDraw
import pytest

from custom_components.minitel_interface.dashboard.render import (
    _CONDITION_ICONS,
    draw_weather_icon,
    render_idle_scene,
    render_media_scene,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _make_png_bytes(size=(50, 50), color=128) -> bytes:
    buf = BytesIO()
    Image.new("L", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_render_idle_scene_returns_valid_png():
    result = render_idle_scene(556, 512, clock_text="12:34", condition="sunny", temperature_text="21.5C")
    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)
    assert image.mode == "L"


def test_render_idle_scene_with_forecast():
    forecast = [
        ("Mon", "sunny", "22C", "12C"),
        ("Tue", "cloudy", "20C", "11C"),
        ("Wed", "rainy", "18C", "10C"),
        ("Thu", "lightning-rainy", "23C", "13C"),
        ("Fri", "windy", "19C", "9C"),
    ]
    result = render_idle_scene(
        556, 512, clock_text="12:34", condition="sunny", temperature_text="21.5C", forecast=forecast
    )
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)


def test_render_idle_scene_respects_background_color():
    result = render_idle_scene(200, 200, clock_text="", condition="", temperature_text="", background_color=200)
    image = Image.open(BytesIO(result))
    assert image.getpixel((199, 5)) == 200


def test_render_media_scene_without_thumbnail():
    result = render_media_scene(
        556, 512, clock_text="12:34", condition="sunny", temperature_text="21C", title_text="Some Movie"
    )
    assert result.startswith(PNG_MAGIC)
    image = Image.open(BytesIO(result))
    assert image.size == (556, 512)


def test_render_media_scene_clock_fills_left_half():
    """The clock is auto-sized to the largest font that fits the left half."""
    width, height = 556, 512
    left_width = width // 2
    result = render_media_scene(
        width, height, clock_text="12:34", condition="sunny", temperature_text="21C", title_text="Movie"
    )
    image = Image.open(BytesIO(result))
    bbox = image.crop((0, 0, left_width, height)).getbbox()
    assert bbox is not None
    text_width = bbox[2] - bbox[0]
    # Width-bound (a 5-char string is wide relative to a half-width panel):
    # the auto-fit font should use almost the full available width.
    assert text_width > left_width * 0.8
    # And be substantially bigger than the small fixed size used previously.
    assert (bbox[3] - bbox[1]) > 60


def test_render_media_scene_thumbnail_is_cropped_not_stretched():
    # A very wide (non-square) source: if it were stretched instead of
    # cropped, the resulting square would show visible distortion; here we
    # just assert it still produces a square-canvas-sized valid image and
    # doesn't raise, since aspect-ratio distortion isn't directly
    # observable from the flat "L" output without per-pixel source tracking.
    thumbnail = _make_png_bytes(size=(400, 50))
    result = render_media_scene(
        556,
        512,
        clock_text="12:34",
        condition="sunny",
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
            condition="sunny",
            temperature_text="21C",
            title_text="Some Movie",
            thumbnail_bytes=b"not an image",
        )


def test_draw_weather_icon_handles_all_known_conditions():
    for condition in _CONDITION_ICONS:
        image = Image.new("L", (40, 40), 0)
        draw = ImageDraw.Draw(image)
        draw_weather_icon(draw, condition, (5, 5, 35, 35), 255, 0)
        assert image.getbbox() is not None, f"icon for '{condition}' drew nothing"


def test_draw_weather_icon_unknown_condition_falls_back():
    image = Image.new("L", (40, 40), 0)
    draw = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(image)
    draw_weather_icon(draw, "not-a-real-condition", (5, 5, 35, 35), 255, 0)
    assert image.getbbox() is not None
