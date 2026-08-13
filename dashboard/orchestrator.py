"""Orchestrates the periodic Minitel dashboard render.

Picks the media scene (clock+weather left, thumbnail/logo+title right) when
something is playing, falls back to the idle scene (big clock + weather +
forecast) otherwise, and skips entirely when the dashboard switch is off
(e.g. while a fullscreen video is being shown manually - see switch.py).

Updates are triggered by: the periodic timer (DASHBOARD_INTERVAL, see
__init__.py - keeps the clock fresh even when nothing else changes), an
immediate render at integration startup, and a state-change listener on the
configured media_player (so artwork/title updates land as soon as the
content changes, not up to a minute late).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..const import (
    CONF_DASHBOARD_HEIGHT,
    CONF_DASHBOARD_LOGO_DIR,
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

# Attributes that actually affect what's rendered - media_player entities
# often update media_position every few seconds, which would otherwise
# trigger a re-render (and a wm-server round-trip) way more often than
# needed.
_RELEVANT_MEDIA_ATTRS = ("media_title", "entity_picture", "app_name", "source")


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
        image_bytes = await scenes.async_render_media_scene(
            hass,
            media_player_entity,
            weather_entity,
            width,
            height,
            logo_dir=options.get(CONF_DASHBOARD_LOGO_DIR),
        )

    if image_bytes is None:
        image_bytes = await scenes.async_render_idle_scene(hass, weather_entity, width, height)

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


def _media_signature(state) -> tuple | None:
    if state is None:
        return None
    return (state.state, tuple(state.attributes.get(attr) for attr in _RELEVANT_MEDIA_ATTRS))


def async_track_media_player_changes(hass: HomeAssistant, entry: ConfigEntry, coordinator: MinitelCoordinator):
    """Re-render the dashboard whenever the configured media_player's content changes.

    Returns the listener's remove callback (pass it to entry.async_on_unload),
    or None if no media_player is configured for the dashboard.
    """
    media_player_entity = entry.options.get(CONF_DASHBOARD_MEDIA_PLAYER_ENTITY)
    if media_player_entity is None:
        return None

    @callback
    def _async_state_changed(event: Event[EventStateChangedData]) -> None:
        if _media_signature(event.data["old_state"]) == _media_signature(event.data["new_state"]):
            return
        hass.async_create_task(async_update_dashboard(hass, entry, coordinator))

    return async_track_state_change_event(hass, [media_player_entity], _async_state_changed)
