"""Scene selection & rendering for the Minitel dashboard.

Bridges Home Assistant state (media_player/weather entities) to the pure
Pillow helpers in dashboard/render.py. Blocking image work (PIL, font
loading) always runs via hass.async_add_executor_job - it must never run on
the event loop. Any failure to fetch/decode artwork or forecast data falls
back gracefully (empty forecast, no thumbnail, scene returns None) rather
than raising, so the orchestrator can fall back to the idle scene instead of
leaving the display stuck or crashing the timer.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
import logging
from pathlib import Path
import re

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from . import render

_LOGGER = logging.getLogger(__name__)

CLOCK_FORMAT = "%H:%M"
FORECAST_DAYS = 5


@dataclass(frozen=True)
class WeatherNow:
    condition: str
    temperature_text: str


@dataclass(frozen=True)
class ForecastDay:
    label: str
    condition: str
    high_text: str
    low_text: str


def _format_temperature(value: float | None, unit: str | None) -> str:
    if value is None:
        return ""
    return f"{value}{unit or ''}"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


async def async_get_weather_now(hass: HomeAssistant, weather_entity: str) -> WeatherNow:
    state = hass.states.get(weather_entity)
    if state is None:
        return WeatherNow(condition="", temperature_text="")
    unit = state.attributes.get("temperature_unit")
    return WeatherNow(
        condition=state.state,
        temperature_text=_format_temperature(state.attributes.get("temperature"), unit),
    )


async def async_get_weather_forecast(
    hass: HomeAssistant, weather_entity: str, days: int = FORECAST_DAYS
) -> list[ForecastDay]:
    """Fetch the daily forecast via the weather.get_forecasts service."""
    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "daily"},
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError as err:
        _LOGGER.warning("failed to fetch forecast for %s: %s", weather_entity, err)
        return []

    entries = (response or {}).get(weather_entity, {}).get("forecast", [])
    state = hass.states.get(weather_entity)
    unit = state.attributes.get("temperature_unit") if state is not None else None

    forecast: list[ForecastDay] = []
    for entry in entries[:days]:
        entry_dt = dt_util.parse_datetime(entry.get("datetime", "")) or dt_util.now()
        forecast.append(
            ForecastDay(
                label=entry_dt.strftime("%a"),
                condition=entry.get("condition") or "",
                high_text=_format_temperature(entry.get("temperature"), unit),
                low_text=_format_temperature(entry.get("templow"), unit),
            )
        )
    return forecast


async def _async_fetch_url(hass: HomeAssistant, url: str) -> bytes | None:
    if url.startswith("/"):
        try:
            url = get_url(hass, allow_internal=True, allow_external=False) + url
        except NoURLAvailableError as err:
            _LOGGER.warning("no internal URL available to resolve '%s': %s", url, err)
            return None

    session = async_get_clientsession(hass)
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()
    except OSError as err:
        _LOGGER.warning("failed to fetch '%s': %s", url, err)
        return None


async def async_resolve_media_thumbnail(
    hass: HomeAssistant, media_player_entity: str, logo_dir: str | None
) -> bytes | None:
    """Return the media artwork if available, else a service logo, else None.

    Logos are looked up as `<logo_dir>/<slugified app_name>.png`, falling
    back to `<logo_dir>/default.png` - both are user-supplied files, not
    bundled with the integration (no third-party logos are shipped in this
    repo), and must live under a Home Assistant allowed path.
    """
    state = hass.states.get(media_player_entity)
    if state is None:
        return None

    picture_path = state.attributes.get("entity_picture")
    if picture_path:
        artwork = await _async_fetch_url(hass, picture_path)
        if artwork is not None:
            return artwork

    if not logo_dir:
        return None

    app_name = state.attributes.get("app_name") or state.attributes.get("source")
    candidates = []
    if app_name:
        candidates.append(Path(logo_dir) / f"{_slugify(app_name)}.png")
    candidates.append(Path(logo_dir) / "default.png")

    for candidate in candidates:
        candidate_str = str(candidate)
        if not hass.config.is_allowed_path(candidate_str):
            continue
        try:
            return await hass.async_add_executor_job(candidate.read_bytes)
        except OSError:
            continue
    return None


async def async_render_idle_scene(
    hass: HomeAssistant, weather_entity: str, width: int, height: int, *, font_path: str | None = None
) -> bytes:
    """Clock (big) on top, current conditions + forecast row on the bottom."""
    now = await async_get_weather_now(hass, weather_entity)
    forecast = await async_get_weather_forecast(hass, weather_entity)
    clock_text = dt_util.now().strftime(CLOCK_FORMAT)

    forecast_tuples = [(day.label, day.condition, day.high_text, day.low_text) for day in forecast]

    return await hass.async_add_executor_job(
        partial(
            render.render_idle_scene,
            width,
            height,
            clock_text=clock_text,
            condition=now.condition,
            temperature_text=now.temperature_text,
            forecast=forecast_tuples,
            font_path=font_path,
        )
    )


async def async_render_media_scene(
    hass: HomeAssistant,
    media_player_entity: str,
    weather_entity: str,
    width: int,
    height: int,
    *,
    logo_dir: str | None = None,
    font_path: str | None = None,
) -> bytes | None:
    """Clock + current conditions on the left, thumbnail + title on the right.

    Returns None if nothing is playing, so the orchestrator falls back to
    the idle scene.
    """
    state = hass.states.get(media_player_entity)
    if state is None or state.state != "playing":
        return None

    title = state.attributes.get("media_title") or state.name
    thumbnail_bytes = await async_resolve_media_thumbnail(hass, media_player_entity, logo_dir)
    now = await async_get_weather_now(hass, weather_entity)
    clock_text = dt_util.now().strftime(CLOCK_FORMAT)

    try:
        return await hass.async_add_executor_job(
            partial(
                render.render_media_scene,
                width,
                height,
                clock_text=clock_text,
                condition=now.condition,
                temperature_text=now.temperature_text,
                title_text=title,
                thumbnail_bytes=thumbnail_bytes,
                font_path=font_path,
            )
        )
    except ValueError as err:
        _LOGGER.warning("failed to render media scene for %s: %s", media_player_entity, err)
        return None
