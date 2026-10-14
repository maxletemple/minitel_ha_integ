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


def _window(index: int) -> WinSummary:
    return WinSummary(index=index, pos_x=0, pos_y=0, width=100, height=100, background_color=0, objects=())


async def test_coordinator_clears_windows_after_reconnection(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="minitel_interface")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.connect_count = 1
    client.async_get_summary.return_value = [_window(0), _window(1)]

    coordinator = MinitelCoordinator(hass, entry, client, scan_interval=10)
    await coordinator.async_refresh()
    assert coordinator.consume_reconnected() is False
    client.async_win_destroy.assert_not_called()

    client.connect_count = 2  # connection lost, then lazily re-established
    await coordinator.async_refresh()

    assert [c.args for c in client.async_win_destroy.call_args_list] == [(1,), (0,)]
    assert coordinator.data == []
    assert coordinator.consume_reconnected() is True
    assert coordinator.consume_reconnected() is False

    client.async_win_destroy.reset_mock()
    await coordinator.async_refresh()
    client.async_win_destroy.assert_not_called()


async def test_coordinator_retries_clear_when_it_fails(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="minitel_interface")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.connect_count = 1
    client.async_get_summary.return_value = [_window(0)]

    coordinator = MinitelCoordinator(hass, entry, client, scan_interval=10)
    await coordinator.async_refresh()

    client.connect_count = 2
    client.async_win_destroy.side_effect = WmConnectionError("connection lost")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator.consume_reconnected() is False

    client.connect_count = 3
    client.async_win_destroy.side_effect = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.consume_reconnected() is True
