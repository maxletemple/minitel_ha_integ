"""Diagnostics support for the Minitel Interface integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, DOMAIN
from .coordinator import MinitelCoordinator

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator: MinitelCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    windows = coordinator.data or []
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "connected": coordinator.client.connected,
        "last_update_success": coordinator.last_update_success,
        "windows": [
            {
                "index": win.index,
                "pos_x": win.pos_x,
                "pos_y": win.pos_y,
                "width": win.width,
                "height": win.height,
                "background_color": win.background_color,
                "objects": [{"index": obj.index, "type": obj.data_type} for obj in win.objects],
            }
            for win in windows
        ],
    }
