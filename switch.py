"""Switch controlling whether the Minitel dashboard timer pushes frames.

Turning this off leaves the screen untouched, freeing the window/object for
manual use (e.g. a fullscreen video) without the periodic dashboard render
fighting over it.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_HOST, CONF_PORT, DOMAIN

DASHBOARD_SWITCH_DESCRIPTION = SwitchEntityDescription(key="dashboard_enabled", name="Dashboard")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    switch = MinitelDashboardSwitch(entry)
    hass.data[DOMAIN][entry.entry_id]["dashboard_switch"] = switch
    async_add_entities([switch])


class MinitelDashboardSwitch(SwitchEntity, RestoreEntity):
    """Enables/disables the periodic dashboard render (clock/weather/media art).

    State is kept in memory (no wm-server round-trip): the dashboard
    orchestrator checks `is_on` before pushing a frame. Restored across HA
    restarts via RestoreEntity so a manual "off" (e.g. before a fullscreen
    video) survives a restart.
    """

    entity_description = DASHBOARD_SWITCH_DESCRIPTION
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_dashboard_enabled"
        self._attr_is_on = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Minitel display server",
            configuration_url=f"tcp://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
