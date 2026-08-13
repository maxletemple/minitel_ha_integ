"""Scene selection & rendering for the Minitel dashboard.

Bridges Home Assistant state (media_player/weather entities) to the pure
Pillow helpers in dashboard/render.py. Blocking image work (PIL, font
loading) always runs via hass.async_add_executor_job - it must never run on
the event loop. Any failure to fetch/decode artwork falls back to None
rather than raising, so the orchestrator can fall back to the clock/weather
scene instead of leaving the display stuck or crashing the timer.
"""

from __future__ import annotations

from functools import partial
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from . import render

_LOGGER = logging.getLogger(__name__)

CLOCK_FORMAT = "%H:%M"


def _resolve_picture_url(hass: HomeAssistant, picture_path: str) -> str:
    if not picture_path.startswith("/"):
        return picture_path
    return get_url(hass, allow_internal=True, allow_external=False) + picture_path


async def async_render_media_art_scene(
    hass: HomeAssistant, media_player_entity: str, width: int, height: int
) -> bytes | None:
    """Return a composed artwork+title PNG, or None if nothing is playing."""
    state = hass.states.get(media_player_entity)
    if state is None or state.state != "playing":
        return None

    picture_path = state.attributes.get("entity_picture")
    if not picture_path:
        return None

    try:
        picture_url = _resolve_picture_url(hass, picture_path)
        session = async_get_clientsession(hass)
        async with session.get(picture_url) as response:
            response.raise_for_status()
            artwork_bytes = await response.read()
    except (NoURLAvailableError, OSError) as err:
        _LOGGER.warning("failed to fetch artwork for %s: %s", media_player_entity, err)
        return None

    title = state.attributes.get("media_title") or state.name

    try:
        return await hass.async_add_executor_job(
            partial(render.compose_media_art, width, height, artwork_bytes, title)
        )
    except ValueError as err:
        _LOGGER.warning("failed to render artwork for %s: %s", media_player_entity, err)
        return None


async def async_render_clock_weather_scene(
    hass: HomeAssistant, weather_entity: str, width: int, height: int
) -> bytes:
    """Return the fallback clock+weather widget PNG."""
    state = hass.states.get(weather_entity)
    condition_text = state.state if state is not None else ""
    temperature = state.attributes.get("temperature") if state is not None else None
    unit = state.attributes.get("temperature_unit") if state is not None else None
    temperature_text = f"{temperature}{unit or ''}" if temperature is not None else ""

    clock_text = dt_util.now().strftime(CLOCK_FORMAT)

    return await hass.async_add_executor_job(
        partial(
            render.render_clock_weather,
            width,
            height,
            clock_text=clock_text,
            condition_text=condition_text,
            temperature_text=temperature_text,
        )
    )
