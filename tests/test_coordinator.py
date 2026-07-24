"""Tests for MinitelCoordinator."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.minitel_interface.coordinator import MinitelCoordinator
from custom_components.minitel_interface.wmclient import WinSummary, WmConnectionError


async def test_coordinator_returns_summary(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="minitel_interface")
    entry.add_to_hass(hass)
    client = AsyncMock()
    windows = [WinSummary(index=0, pos_x=0, pos_y=0, width=100, height=100, background_color=0, objects=())]
    client.async_get_summary.return_value = windows

    coordinator = MinitelCoordinator(hass, entry, client, scan_interval=10)
    await coordinator.async_refresh()

    assert coordinator.data == windows
    assert coordinator.last_update_success is True


async def test_coordinator_update_failed_on_wm_error(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="minitel_interface")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_get_summary.side_effect = WmConnectionError("connection lost")

    coordinator = MinitelCoordinator(hass, entry, client, scan_interval=10)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
