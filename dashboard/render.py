"""Pure Pillow rendering helpers for the Minitel dashboard.

No dependency on Home Assistant - operates on plain strings/bytes so it can
be unit-tested directly, in the spirit of wmclient/protocol.py. wm-server
converts any PNG to 8-bit grayscale server-side (see PROTOCOL.md), so images
are composed directly in "L" mode to keep bytes small and avoid surprises.

Weather conditions are drawn as small procedural icons (sun, cloud, rain...)
rather than text: at the display's low resolution, a chunky ~30px pictogram
reads far better than a condition word, and it sidesteps ever needing to
bundle/license third-party icon sets.

Two scenes:
- render_idle_scene: nothing playing - big clock on the top half, current
  conditions + a multi-day forecast row (with icons) on the bottom half.
- render_media_scene: something playing - a huge clock fills the left half;
  the top-right quadrant holds a center-cropped square thumbnail (artwork or
  a fallback service logo, resolved upstream by dashboard.scenes); the
  bottom-right quadrant holds the current weather icon/temperature and the
  title.
"""

from __future__ import annotations

from io import BytesIO
import math

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

_MARGIN = 8
_THUMBNAIL_MARGIN = 10
_BAND_HEIGHT_RATIO = 0.28  # bottom title band height, as a fraction of the thumbnail's height
_ELLIPSIS = "..."
_DEFAULT_ICON_SIZE = 30


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
    if not text or max_width <= 0 or draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + _ELLIPSIS, font=font) > max_width:
        text = text[:-1]
    return (text + _ELLIPSIS) if text else _ELLIPSIS


def _fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str | None,
    max_width: int,
    max_height: int,
    *,
    min_size: int = 10,
    max_size: int = 400,
) -> int:
    """Largest font size (binary search) whose textbbox fits within max_width x max_height.

    The bundled default font's glyph metrics don't scale linearly with the
    requested size, so a fixed "big" size doesn't reliably fill a given box
    across different configured dashboard dimensions - measuring is more
    robust than guessing a constant.
    """
    best_size = min_size
    low, high = min_size, max_size
    while low <= high:
        mid = (low + high) // 2
        font = _load_font(font_path, mid)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width and (bbox[3] - bbox[1]) <= max_height:
            best_size = mid
            low = mid + 1
        else:
            high = mid - 1
    return best_size


def _wrap_two_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap into at most two lines, ellipsizing the rest."""
    if not text or draw.textlength(text, font=font) <= max_width:
        return [text] if text else []

    words = text.split()
    first_words: list[str] = []
    remaining = list(words)
    while remaining:
        candidate = " ".join([*first_words, remaining[0]])
        if not first_words or draw.textlength(candidate, font=font) <= max_width:
            first_words.append(remaining.pop(0))
        else:
            break

    first_line = " ".join(first_words)
    second_line = _fit_text(draw, " ".join(remaining), font, max_width) if remaining else ""
    return [line for line in (first_line, second_line) if line]


def _crop_to_square(image: Image.Image, side: int) -> Image.Image:
    """Scale (preserving aspect ratio) then center-crop to a side x side square."""
    width, height = image.size
    scale = side / min(width, height)
    resized = image.resize((max(round(width * scale), 1), max(round(height * scale), 1)), Image.LANCZOS)
    rw, rh = resized.size
    left = (rw - side) // 2
    top = (rh - side) // 2
    return resized.crop((left, top, left + side, top + side))


def _decode_grayscale(image_bytes: bytes, *, what: str) -> Image.Image:
    try:
        image = Image.open(BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError) as err:
        raise ValueError(f"cannot decode {what}: {err}") from err
    return image.convert("L")


# --- Weather icon drawing -----------------------------------------------
#
# Each _icon_* function draws a condition's pictogram inside `box`
# (x0, y0, x1, y1), in `color`, using `bg_color` only where a shape needs to
# be "cut out" (e.g. the moon's crescent). Building blocks (_draw_sun,
# _draw_cloud, ...) are reused across several conditions.


def _draw_sun(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int) -> None:
    x0, y0, x1, y1 = box
    size = min(x1 - x0, y1 - y0)
    cx, cy = x0 + size / 2, y0 + size / 2
    r = size * 0.26
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    r_in, r_out = size * 0.34, size * 0.48
    width = max(int(size * 0.08), 1)
    for i in range(8):
        angle = math.radians(i * 45)
        x_in, y_in = cx + r_in * math.cos(angle), cy + r_in * math.sin(angle)
        x_out, y_out = cx + r_out * math.cos(angle), cy + r_out * math.sin(angle)
        draw.line((x_in, y_in, x_out, y_out), fill=color, width=width)


def _draw_moon(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int, bg_color: int) -> None:
    x0, y0, x1, y1 = box
    size = min(x1 - x0, y1 - y0)
    cx, cy = x0 + size / 2, y0 + size / 2
    r = size * 0.34
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    cut_r = r * 0.85
    cut_cx = cx + r * 0.5
    draw.ellipse((cut_cx - cut_r, cy - cut_r, cut_cx + cut_r, cy + cut_r), fill=bg_color)


def _draw_cloud(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    draw.ellipse((x0 + w * 0.05, y0 + h * 0.30, x0 + w * 0.55, y0 + h * 0.80), fill=color)
    draw.ellipse((x0 + w * 0.30, y0 + h * 0.05, x0 + w * 0.80, y0 + h * 0.60), fill=color)
    draw.ellipse((x0 + w * 0.50, y0 + h * 0.30, x0 + w * 0.98, y0 + h * 0.80), fill=color)
    draw.rectangle((x0 + w * 0.08, y0 + h * 0.55, x0 + w * 0.92, y0 + h * 0.80), fill=color)


def _draw_raindrops(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int, count: int) -> None:
    x0, y0, x1, y1 = box
    if y1 <= y0:
        return
    step = (x1 - x0) / (count + 1)
    line_len = (y1 - y0) * 0.85
    lw = max(int((y1 - y0) * 0.22), 1)
    for i in range(count):
        x = x0 + step * (i + 1)
        draw.line((x, y0, x - line_len * 0.35, y0 + line_len), fill=color, width=lw)


def _draw_snowflakes(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int, count: int) -> None:
    x0, y0, x1, y1 = box
    if y1 <= y0:
        return
    step = (x1 - x0) / (count + 1)
    r = min(step, y1 - y0) * 0.4
    for i in range(count):
        cx = x0 + step * (i + 1)
        cy = (y0 + y1) / 2
        for angle_deg in (0, 60, 120):
            angle = math.radians(angle_deg)
            dx, dy = r * math.cos(angle), r * math.sin(angle)
            draw.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=color, width=1)


def _draw_bolt(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    points = [
        (x0 + w * 0.55, y0),
        (x0 + w * 0.20, y0 + h * 0.55),
        (x0 + w * 0.45, y0 + h * 0.55),
        (x0 + w * 0.30, y0 + h),
        (x0 + w * 0.75, y0 + h * 0.40),
        (x0 + w * 0.48, y0 + h * 0.40),
    ]
    draw.polygon(points, fill=color)


def _draw_fog_lines(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int, count: int = 4) -> None:
    x0, y0, x1, y1 = box
    step = (y1 - y0) / (count + 1)
    lw = max(int((y1 - y0) * 0.08), 1)
    for i in range(count):
        y = y0 + step * (i + 1)
        inset = (x1 - x0) * (0.05 if i % 2 == 0 else 0.18)
        draw.line((x0 + inset, y, x1 - inset, y), fill=color, width=lw)


def _draw_wind_lines(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int, count: int = 3) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    step = h / (count + 1)
    lw = max(int(h * 0.08), 1)
    for i in range(count):
        y = y0 + step * (i + 1)
        amplitude = h * 0.10
        line_w = w * (0.95 - i * 0.15)
        segments = 12
        points = [
            (x0 + line_w * (s / segments), y + amplitude * math.sin(s / segments * math.pi * 2))
            for s in range(segments + 1)
        ]
        draw.line(points, fill=color, width=lw)


def _draw_warning(draw: ImageDraw.ImageDraw, box: tuple[float, float, float, float], color: int) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    draw.polygon([(x0 + w / 2, y0), (x0, y1), (x1, y1)], outline=color, width=max(int(w * 0.06), 1))
    draw.line((x0 + w / 2, y0 + h * 0.3, x0 + w / 2, y0 + h * 0.65), fill=color, width=max(int(w * 0.1), 1))
    r = w * 0.05
    cx, cy = x0 + w / 2, y0 + h * 0.8
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)


def _icon_sunny(draw, box, color, bg_color):
    _draw_sun(draw, box, color)


def _icon_clear_night(draw, box, color, bg_color):
    _draw_moon(draw, box, color, bg_color)


def _icon_cloudy(draw, box, color, bg_color):
    _draw_cloud(draw, box, color)


def _icon_partlycloudy(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    _draw_sun(draw, (x0, y0, x0 + w * 0.6, y0 + h * 0.6), color)
    _draw_cloud(draw, (x0 + w * 0.15, y0 + h * 0.25, x1, y1), color)


def _icon_fog(draw, box, color, bg_color):
    _draw_fog_lines(draw, box, color)


def _icon_windy(draw, box, color, bg_color):
    _draw_wind_lines(draw, box, color)


def _icon_windy_variant(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    _draw_cloud(draw, (x0, y0, x1, y0 + h * 0.55), color)
    _draw_wind_lines(draw, (x0, y0 + h * 0.62, x1, y1), color, count=2)


def _icon_rainy(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    cloud_bottom = y0 + h * 0.55
    _draw_cloud(draw, (x0, y0, x1, cloud_bottom), color)
    _draw_raindrops(draw, (x0, cloud_bottom, x1, y1), color, count=3)


def _icon_pouring(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    cloud_bottom = y0 + h * 0.5
    _draw_cloud(draw, (x0, y0, x1, cloud_bottom), color)
    _draw_raindrops(draw, (x0, cloud_bottom, x1, y1), color, count=5)


def _icon_snowy(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    cloud_bottom = y0 + h * 0.55
    _draw_cloud(draw, (x0, y0, x1, cloud_bottom), color)
    _draw_snowflakes(draw, (x0, cloud_bottom, x1, y1), color, count=3)


def _icon_snowy_rainy(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    cloud_bottom = y0 + h * 0.55
    _draw_cloud(draw, (x0, y0, x1, cloud_bottom), color)
    mid = (x0 + x1) / 2
    _draw_raindrops(draw, (x0, cloud_bottom, mid, y1), color, count=1)
    _draw_snowflakes(draw, (mid, cloud_bottom, x1, y1), color, count=1)


def _icon_hail(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    cloud_bottom = y0 + h * 0.55
    _draw_cloud(draw, (x0, y0, x1, cloud_bottom), color)
    w = x1 - x0
    step = w / 4
    r = min(step, y1 - cloud_bottom) * 0.25
    cy = cloud_bottom + (y1 - cloud_bottom) / 2
    for i in range(3):
        cx = x0 + step * (i + 1)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)


def _icon_lightning(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    cloud_bottom = y0 + h * 0.55
    _draw_cloud(draw, (x0, y0, x1, cloud_bottom), color)
    w = x1 - x0
    _draw_bolt(draw, (x0 + w * 0.25, cloud_bottom - h * 0.05, x1 - w * 0.25, y1), color)


def _icon_lightning_rainy(draw, box, color, bg_color):
    x0, y0, x1, y1 = box
    h = y1 - y0
    cloud_bottom = y0 + h * 0.5
    _draw_cloud(draw, (x0, y0, x1, cloud_bottom), color)
    mid = (x0 + x1) / 2
    _draw_bolt(draw, (x0, cloud_bottom - h * 0.05, mid, y1), color)
    _draw_raindrops(draw, (mid, cloud_bottom, x1, y1), color, count=2)


def _icon_exceptional(draw, box, color, bg_color):
    _draw_warning(draw, box, color)


_CONDITION_ICONS = {
    "sunny": _icon_sunny,
    "clear-night": _icon_clear_night,
    "cloudy": _icon_cloudy,
    "partlycloudy": _icon_partlycloudy,
    "fog": _icon_fog,
    "windy": _icon_windy,
    "windy-variant": _icon_windy_variant,
    "rainy": _icon_rainy,
    "pouring": _icon_pouring,
    "snowy": _icon_snowy,
    "snowy-rainy": _icon_snowy_rainy,
    "hail": _icon_hail,
    "lightning": _icon_lightning,
    "lightning-rainy": _icon_lightning_rainy,
    "exceptional": _icon_exceptional,
}


def draw_weather_icon(
    draw: ImageDraw.ImageDraw, condition: str, box: tuple[float, float, float, float], color: int, bg_color: int
) -> None:
    """Draw a condition pictogram inside `box`. Unknown conditions fall back to a cloud."""
    icon_fn = _CONDITION_ICONS.get(condition, _icon_cloudy)
    icon_fn(draw, box, color, bg_color)


# --- Scenes ---------------------------------------------------------------


def _draw_weather_column(
    draw: ImageDraw.ImageDraw,
    x0: float,
    x1: float,
    top_y: float,
    *,
    label: str,
    condition: str,
    temp_text: str,
    label_font_size: int,
    icon_size: int,
    temp_font_size: int,
    text_color: int,
    background_color: int,
    font_path: str | None,
) -> None:
    """Draw one [label] / icon / temperature column, centered between x0 and x1."""
    center_x = (x0 + x1) / 2
    max_width = x1 - x0 - 2 * _MARGIN
    y = top_y

    if label:
        label_font = _load_font(font_path, label_font_size)
        fitted_label = _fit_text(draw, label, label_font, max_width)
        label_width = draw.textlength(fitted_label, font=label_font)
        draw.text((center_x - label_width / 2, y), fitted_label, fill=text_color, font=label_font)
        y += label_font_size + _MARGIN

    icon_x = center_x - icon_size / 2
    draw_weather_icon(draw, condition, (icon_x, y, icon_x + icon_size, y + icon_size), text_color, background_color)
    y += icon_size + _MARGIN

    temp_font = _load_font(font_path, temp_font_size)
    fitted_temp = _fit_text(draw, temp_text, temp_font, max_width)
    temp_width = draw.textlength(fitted_temp, font=temp_font)
    draw.text((center_x - temp_width / 2, y), fitted_temp, fill=text_color, font=temp_font)


def render_idle_scene(
    width: int,
    height: int,
    *,
    clock_text: str,
    condition: str,
    temperature_text: str,
    forecast: list[tuple[str, str, str]] = (),
    background_color: int = 0,
    text_color: int = 255,
    clock_font_size: int | None = None,
    now_temp_font_size: int = 32,
    now_icon_size: int = 40,
    forecast_font_size: int = 22,
    forecast_icon_size: int = _DEFAULT_ICON_SIZE,
    font_path: str | None = None,
) -> bytes:
    """Top half: big clock. Bottom half: a row of weather columns.

    The first column is the current conditions (no label, bigger icon and
    font); the rest is `forecast` - a list of (day_label, condition,
    max_temp_text) tuples, soonest first, up to 4 columns, sharing the same
    label/icon/temperature layout at a smaller size. `clock_font_size`
    defaults to the largest size that fits the top half (see _fit_font_size).
    """
    image = Image.new("L", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    if clock_font_size is None:
        clock_font_size = _fit_font_size(
            draw, clock_text, font_path, width - 2 * _MARGIN, height // 2 - 2 * _MARGIN
        )
    clock_font = _load_font(font_path, clock_font_size)
    clock_bbox = draw.textbbox((0, 0), clock_text, font=clock_font)
    clock_x = max((width - (clock_bbox[2] - clock_bbox[0])) // 2, _MARGIN)
    clock_y = max((height // 2 - (clock_bbox[3] - clock_bbox[1])) // 2, _MARGIN)
    draw.text((clock_x, clock_y), clock_text, fill=text_color, font=clock_font)

    forecast = list(forecast[:4])
    row_top = height // 2 + _MARGIN * 2

    now_weight = 1.3
    day_weight = 1.0
    weights = [now_weight] + [day_weight] * len(forecast)
    total_weight = sum(weights)
    column_bounds = []
    x = 0.0
    for weight in weights:
        column_width = width * weight / total_weight
        column_bounds.append((x, x + column_width))
        x += column_width
    if column_bounds:
        column_bounds[-1] = (column_bounds[-1][0], width)

    if forecast:
        day_column_width = column_bounds[1][1] - column_bounds[1][0]
        max_label_width = day_column_width - 2 * _MARGIN
        forecast_font_size = min(
            _fit_font_size(draw, day_label, font_path, max_label_width, forecast_font_size * 2)
            for day_label, _, _ in forecast
        )

    now_x0, now_x1 = column_bounds[0]
    _draw_weather_column(
        draw,
        now_x0,
        now_x1,
        row_top,
        label="",
        condition=condition,
        temp_text=temperature_text,
        label_font_size=0,
        icon_size=now_icon_size,
        temp_font_size=now_temp_font_size,
        text_color=text_color,
        background_color=background_color,
        font_path=font_path,
    )

    for (day_label, day_condition, max_temp_text), (x0, x1) in zip(forecast, column_bounds[1:]):
        _draw_weather_column(
            draw,
            x0,
            x1,
            row_top,
            label=day_label,
            condition=day_condition,
            temp_text=max_temp_text,
            label_font_size=forecast_font_size,
            icon_size=forecast_icon_size,
            temp_font_size=forecast_font_size,
            text_color=text_color,
            background_color=background_color,
            font_path=font_path,
        )

    return _to_png_bytes(image)


def render_media_scene(
    width: int,
    height: int,
    *,
    clock_text: str,
    condition: str,
    temperature_text: str,
    title_text: str,
    thumbnail_bytes: bytes | None = None,
    background_color: int = 0,
    text_color: int = 255,
    clock_font_size: int | None = None,
    weather_font_size: int = 22,
    title_font_size: int = 18,
    icon_size: int = _DEFAULT_ICON_SIZE,
    font_path: str | None = None,
) -> bytes:
    """Left half: huge clock. Top-right quadrant: cropped square thumbnail.
    Bottom-right quadrant: current conditions + title.

    `thumbnail_bytes` is whatever image dashboard.scenes already resolved
    (media artwork, or a fallback service logo) - drawn either way, cropped
    (never stretched) to a square filling the top-right quadrant minus a
    10px margin. A missing thumbnail just leaves that quadrant blank.
    `clock_font_size` defaults to the largest size that fills the left half
    (see _fit_font_size), so the clock takes up the whole panel.
    """
    image = Image.new("L", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    left_width = width // 2
    if clock_font_size is None:
        clock_font_size = _fit_font_size(draw, clock_text, font_path, left_width - 2 * _MARGIN, height - 2 * _MARGIN)
    clock_font = _load_font(font_path, clock_font_size)
    clock_bbox = draw.textbbox((0, 0), clock_text, font=clock_font)
    clock_w, clock_h = clock_bbox[2] - clock_bbox[0], clock_bbox[3] - clock_bbox[1]
    clock_x = max((left_width - clock_w) // 2, _MARGIN)
    clock_y = max((height - clock_h) // 2, _MARGIN)
    draw.text((clock_x, clock_y), clock_text, fill=text_color, font=clock_font)

    half_height = height // 2

    # Top-right quadrant: cropped square thumbnail.
    if thumbnail_bytes is not None:
        quadrant_w = width - left_width
        side = min(quadrant_w, half_height) - 2 * _THUMBNAIL_MARGIN
        if side > 0:
            source = _decode_grayscale(thumbnail_bytes, what="thumbnail")
            square = _crop_to_square(source, side)
            square_x = left_width + (quadrant_w - side) // 2
            square_y = (half_height - side) // 2
            image.paste(square, (square_x, square_y))

    # Bottom-right quadrant: current conditions + title.
    quadrant_x0, quadrant_y0 = left_width, half_height
    quadrant_x1, quadrant_y1 = width, height
    quadrant_w = quadrant_x1 - quadrant_x0

    weather_font = _load_font(font_path, weather_font_size)
    icon_x0, icon_y0 = quadrant_x0 + _MARGIN, quadrant_y0 + _MARGIN
    draw_weather_icon(
        draw, condition, (icon_x0, icon_y0, icon_x0 + icon_size, icon_y0 + icon_size), text_color, background_color
    )
    text_y = icon_y0 + (icon_size - weather_font_size) // 2
    draw.text((icon_x0 + icon_size + _MARGIN, text_y), temperature_text, fill=text_color, font=weather_font)

    title_font = _load_font(font_path, title_font_size)
    title_top = icon_y0 + icon_size + _MARGIN * 2
    title_max_width = quadrant_w - 2 * _MARGIN
    for line_index, line in enumerate(_wrap_two_lines(draw, title_text, title_font, title_max_width)):
        line_y = min(title_top + line_index * (title_font_size + 4), quadrant_y1 - title_font_size - _MARGIN)
        draw.text((quadrant_x0 + _MARGIN, line_y), line, fill=text_color, font=title_font)

    return _to_png_bytes(image)
