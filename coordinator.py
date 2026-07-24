"""DataUpdateCoordinator for wm-server.

wm-server never pushes state on its own: CMD_GET_SUMMARY, polled here, is
the only source of truth for what windows/objects currently exist.
"""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .wmclient import WinSummary, WmClient, WmError

_LOGGER = logging.getLogger(__name__)


class MinitelCoordinator(DataUpdateCoordinator[list[WinSummary]]):
    """Polls wm-server's window/object summary on a fixed interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: WmClient, scan_interval: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> list[WinSummary]:
        try:
            return await self.client.async_get_summary()
        except WmError as err:
            raise UpdateFailed(f"error communicating with wm-server: {err}") from err
