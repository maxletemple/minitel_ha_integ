"""DataUpdateCoordinator for wm-server.

wm-server never pushes state on its own: CMD_GET_SUMMARY, polled here, is
the only source of truth for what windows/objects currently exist.

It also detects lost-then-resumed connections (WmClient.connect_count
changed since the last successful poll, whichever command did the lazy
reconnect) and, in that case, destroys every window on wm-server so the
display restarts from a clean slate. Callers learn about it through
consume_reconnected() and are expected to reload whatever they display.
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
        # connect_count as of the last successful poll; None until the first
        # one, so the initial connection isn't mistaken for a reconnection.
        self._seen_connect_count: int | None = None
        self._reconnected = False

    def consume_reconnected(self) -> bool:
        """Return True once after a reconnection reset, then False until the next one."""
        reconnected, self._reconnected = self._reconnected, False
        return reconnected

    async def _async_update_data(self) -> list[WinSummary]:
        try:
            windows = await self.client.async_get_summary()
            if self._seen_connect_count is not None and self.client.connect_count != self._seen_connect_count:
                _LOGGER.info("connection to wm-server resumed, clearing all windows")
                await self._async_clear_windows(windows)
                windows = []
                self._reconnected = True
        except WmError as err:
            # _seen_connect_count is left untouched, so a failed clear is
            # retried on the next poll.
            raise UpdateFailed(f"error communicating with wm-server: {err}") from err

        self._seen_connect_count = self.client.connect_count
        return windows

    async def _async_clear_windows(self, windows: list[WinSummary]) -> None:
        # Highest index first, so destroying one never shifts the index of
        # a window still to be destroyed.
        for window in sorted(windows, key=lambda w: w.index, reverse=True):
            await self.client.async_win_destroy(window.index)
