"""The Minitel Interface integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import MinitelCoordinator
from .dashboard.orchestrator import async_track_media_player_changes, async_update_dashboard
from .services import async_register_services, async_unregister_services
from .wmclient import WmClient, WmError

DASHBOARD_INTERVAL = timedelta(minutes=1)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = WmClient(entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        await client.async_connect()
    except WmError as err:
        raise ConfigEntryNotReady(f"cannot connect to {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}") from err

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = MinitelCoordinator(hass, entry, client, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    is_first_entry = DOMAIN not in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"client": client, "coordinator": coordinator}

    if is_first_entry:
        async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _dashboard_tick(now) -> None:
        await async_update_dashboard(hass, entry, coordinator)

    entry.async_on_unload(async_track_time_interval(hass, _dashboard_tick, DASHBOARD_INTERVAL))

    remove_media_listener = async_track_media_player_changes(hass, entry, coordinator)
    if remove_media_listener is not None:
        entry.async_on_unload(remove_media_listener)

    await async_update_dashboard(hass, entry, coordinator)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    data = hass.data[DOMAIN].pop(entry.entry_id)
    await data["client"].async_close()

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
        async_unregister_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
