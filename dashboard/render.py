"""Pure Pillow rendering helpers for the Minitel dashboard.

No dependency on Home Assistant - operates on plain strings/bytes so it can
be unit-tested directly, in the spirit of wmclient/protocol.py. wm-server
converts any PNG to 8-bit grayscale server-side (see PROTOCOL.md), so images
are composed directly in "L" mode to keep bytes small and avoid surprises.

Two scenes:
- render_idle_scene: nothing playing - big clock on the top half, current
  conditions + a multi-day forecast row on the bottom half.
- render_media_scene: something playing - clock + current conditions on the
  left, thumbnail (artwork or a fallback service logo, resolved upstream by
  dashboard.scenes) + title on the right.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

_MARGIN = 8
_BAND_HEIGHT_RATIO = 0.22  # bottom title band height, as a fraction of the thumbnail's height
_ELLIPSIS = "..."


def _load_font(font_path: str | None, size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    if font_path is None:
        return ImageFont.load_default(size=size)
    try:
        return ImageFont.truetype(font_path, size)
    except OSError as err:
        raise ValueError(f"cannot load font '{font_path}': {err}") from err


def _to_png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    """Truncate text with an ellipsis so it fits within max_width pixels."""
    if max_width <= 0 or draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + _ELLIPSIS, font=font) > max_width:
        text = text[:-1]
    return (text + _ELLIPSIS) if text else _ELLIPSIS


def _decode_grayscale(image_bytes: bytes, size: tuple[int, int], *, what: str) -> Image.Image:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as err:
        raise ValueError(f"cannot decode {what}: {err}") from err
    return image.convert("L").resize(size, Image.LANCZOS)


def render_idle_scene(
    width: int,
    height: int,
    *,
    clock_text: str,
    condition_text: str,
    temperature_text: str,
    forecast: list[tuple[str, str, str, str]] = (),
    background_color: int = 0,
    text_color: int = 255,
    clock_font_size: int = 96,
    weather_font_size: int = 28,
    forecast_font_size: int = 16,
    font_path: str | None = None,
) -> bytes:
    """Top half: big clock. Bottom half: current conditions + forecast row.

    `forecast` is a list of (day_label, condition, high_text, low_text)
    tuples, oldest/soonest first, rendered as up to 5 columns.
    """
    image = Image.new("L", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    clock_font = _load_font(font_path, clock_font_size)
    clock_bbox = draw.textbbox((0, 0), clock_text, font=clock_font)
    clock_x = max((width - (clock_bbox[2] - clock_bbox[0])) // 2, _MARGIN)
    clock_y = max((height // 2 - (clock_bbox[3] - clock_bbox[1])) // 2, _MARGIN)
    draw.text((clock_x, clock_y), clock_text, fill=text_color, font=clock_font)

    bottom_top = height // 2
    weather_font = _load_font(font_path, weather_font_size)
    now_text = f"{condition_text} {temperature_text}".strip()
    draw.text((_MARGIN, bottom_top + _MARGIN), now_text, fill=text_color, font=weather_font)

    if forecast:
        forecast = forecast[:5]
        column_width = width // len(forecast)
        forecast_font = _load_font(font_path, forecast_font_size)
        row_y = bottom_top + _MARGIN * 2 + weather_font_size
        line_height = forecast_font_size + 2
        for i, (day_label, day_condition, high_text, low_text) in enumerate(forecast):
            column_x = i * column_width + _MARGIN
            column_max_width = column_width - 2 * _MARGIN
            lines = [day_label, day_condition, f"{high_text}/{low_text}"]
            for line_index, line in enumerate(lines):
                fitted = _fit_text(draw, line, forecast_font, column_max_width)
                draw.text(
                    (column_x, row_y + line_index * line_height),
                    fitted,
                    fill=text_color,
                    font=forecast_font,
                )

    return _to_png_bytes(image)


def render_media_scene(
    width: int,
    height: int,
    *,
    clock_text: str,
    condition_text: str,
    temperature_text: str,
    title_text: str,
    thumbnail_bytes: bytes | None = None,
    background_color: int = 0,
    text_color: int = 255,
    clock_font_size: int = 40,
    weather_font_size: int = 20,
    title_font_size: int = 18,
    font_path: str | None = None,
) -> bytes:
    """Left half: clock + current conditions. Right half: thumbnail + title.

    `thumbnail_bytes` is whatever image dashboard.scenes already resolved
    (media artwork, or a fallback service logo) - this function draws
    whichever it's given the same way, or leaves the panel blank if None.
    """
    image = Image.new("L", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    left_width = width // 2
    clock_font = _load_font(font_path, clock_font_size)
    weather_font = _load_font(font_path, weather_font_size)

    draw.text((_MARGIN, _MARGIN), clock_text, fill=text_color, font=clock_font)
    now_text = f"{condition_text} {temperature_text}".strip()
    draw.text((_MARGIN, clock_font_size + _MARGIN * 2), now_text, fill=text_color, font=weather_font)

    right_x = left_width
    right_width = width - left_width
    title_font = _load_font(font_path, title_font_size)

    if thumbnail_bytes is not None:
        thumbnail_height = height - title_font_size - 3 * _MARGIN
        thumbnail = _decode_grayscale(thumbnail_bytes, (right_width, thumbnail_height), what="thumbnail")
        image.paste(thumbnail, (right_x, 0))

        band_height = min(max(int(thumbnail_height * _BAND_HEIGHT_RATIO), title_font_size + 2 * _MARGIN), thumbnail_height)
        band_box = (right_x, thumbnail_height - band_height, right_x + right_width, thumbnail_height)
        band = image.crop(band_box)
        darkened_band = Image.blend(band, Image.new("L", band.size, 0), alpha=0.6)
        image.paste(darkened_band, band_box)

        title_y = thumbnail_height - band_height + _MARGIN
    else:
        title_y = height - title_font_size - _MARGIN

    fitted_title = _fit_text(draw, title_text, title_font, right_width - 2 * _MARGIN)
    draw.text((right_x + _MARGIN, title_y), fitted_title, fill=text_color, font=title_font)

    return _to_png_bytes(image)
