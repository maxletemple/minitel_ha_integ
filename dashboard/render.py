"""Pure Pillow rendering helpers for the Minitel dashboard.

No dependency on Home Assistant - operates on plain strings/bytes so it can
be unit-tested directly, in the spirit of wmclient/protocol.py. wm-server
converts any PNG to 8-bit grayscale server-side (see PROTOCOL.md), so images
are composed directly in "L" mode to keep bytes small and avoid surprises.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

_MARGIN = 4
_MEDIA_BAND_HEIGHT_RATIO = 0.22  # bottom title band height, as a fraction of image height


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


def render_clock_weather(
    width: int,
    height: int,
    *,
    clock_text: str,
    condition_text: str,
    temperature_text: str,
    background_color: int = 0,
    text_color: int = 255,
    clock_font_size: int = 32,
    detail_font_size: int = 16,
    font_path: str | None = None,
) -> bytes:
    """Compose the fallback clock+weather widget. Returns PNG bytes ("L" mode)."""
    image = Image.new("L", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    clock_font = _load_font(font_path, clock_font_size)
    detail_font = _load_font(font_path, detail_font_size)

    draw.text((_MARGIN, _MARGIN), clock_text, fill=text_color, font=clock_font)
    draw.text(
        (_MARGIN, clock_font_size + _MARGIN * 2),
        f"{condition_text} {temperature_text}".strip(),
        fill=text_color,
        font=detail_font,
    )

    return _to_png_bytes(image)


def compose_media_art(
    width: int,
    height: int,
    artwork_bytes: bytes,
    title_text: str,
    *,
    text_color: int = 255,
    font_path: str | None = None,
    title_font_size: int = 16,
) -> bytes:
    """Compose an artwork image with a title band. Returns PNG bytes ("L" mode).

    The artwork fills the whole canvas (resized to width x height); the
    title is drawn over a band at the bottom, blended toward black so it
    stays legible regardless of the artwork's own brightness.
    """
    try:
        artwork = Image.open(BytesIO(artwork_bytes))
        artwork.load()
    except (UnidentifiedImageError, OSError) as err:
        raise ValueError(f"cannot decode artwork: {err}") from err

    canvas = artwork.convert("L").resize((width, height), Image.LANCZOS)

    band_height = min(max(int(height * _MEDIA_BAND_HEIGHT_RATIO), title_font_size + 2 * _MARGIN), height)
    band_box = (0, height - band_height, width, height)
    band = canvas.crop(band_box)
    darkened_band = Image.blend(band, Image.new("L", band.size, 0), alpha=0.6)
    canvas.paste(darkened_band, band_box)

    draw = ImageDraw.Draw(canvas)
    font = _load_font(font_path, title_font_size)
    draw.text((_MARGIN, height - band_height + _MARGIN), title_text, fill=text_color, font=font)

    return _to_png_bytes(canvas)
