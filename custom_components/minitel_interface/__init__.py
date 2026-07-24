"""The Minitel Interface integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import MinitelCoordinator
from .services import async_register_services, async_unregister_services
from .wmclient import WmClient, WmError

PLATFORMS = [Platform.SENSOR]


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
