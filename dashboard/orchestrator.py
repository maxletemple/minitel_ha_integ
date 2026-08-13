"""Orchestrates the periodic Minitel dashboard render.

Picks the media-art scene when something is playing, falls back to the
clock+weather scene otherwise, and skips entirely when the dashboard switch
is off (e.g. while a fullscreen video is being shown manually - see
switch.py).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ..const import (
    CONF_DASHBOARD_HEIGHT,
    CONF_DASHBOARD_MEDIA_PLAYER_ENTITY,
    CONF_DASHBOARD_OBJ_INDEX,
    CONF_DASHBOARD_POS_X,
    CONF_DASHBOARD_POS_Y,
    CONF_DASHBOARD_WEATHER_ENTITY,
    CONF_DASHBOARD_WIDTH,
    CONF_DASHBOARD_WIN_INDEX,
    DOMAIN,
)
from ..coordinator import MinitelCoordinator
from ..wmclient import WmError
from . import scenes

_LOGGER = logging.getLogger(__name__)


async def async_update_dashboard(hass: HomeAssistant, entry: ConfigEntry, coordinator: MinitelCoordinator) -> None:
    """Render and push one dashboard frame, unless disabled via the switch.

    Not configured (no dashboard_weather_entity option) means the feature
    is opt-in and off: return immediately without touching the display.
    """
    entry_data = hass.data[DOMAIN][entry.entry_id]
    switch = entry_data.get("dashboard_switch")
    if switch is not None and not switch.is_on:
        return

    options = entry.options
    weather_entity = options.get(CONF_DASHBOARD_WEATHER_ENTITY)
    if weather_entity is None:
        return

    width = options[CONF_DASHBOARD_WIDTH]
    height = options[CONF_DASHBOARD_HEIGHT]

    image_bytes = None
    media_player_entity = options.get(CONF_DASHBOARD_MEDIA_PLAYER_ENTITY)
    if media_player_entity is not None:
        image_bytes = await scenes.async_render_media_art_scene(hass, media_player_entity, width, height)

    if image_bytes is None:
        image_bytes = await scenes.async_render_clock_weather_scene(hass, weather_entity, width, height)

    try:
        await coordinator.client.async_set_object_picture(
            options[CONF_DASHBOARD_WIN_INDEX],
            options[CONF_DASHBOARD_OBJ_INDEX],
            options[CONF_DASHBOARD_POS_X],
            options[CONF_DASHBOARD_POS_Y],
            width,
            height,
            image_bytes,
            is_png=True,
        )
    except WmError as err:
        _LOGGER.warning("failed to push dashboard frame: %s", err)
