"""Tests for dashboard.orchestrator: switch gating and scene fallback wiring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.minitel_interface.const import (
    CONF_DASHBOARD_HEIGHT,
    CONF_DASHBOARD_OBJ_INDEX,
    CONF_DASHBOARD_POS_X,
    CONF_DASHBOARD_POS_Y,
    CONF_DASHBOARD_WEATHER_ENTITY,
    CONF_DASHBOARD_WIDTH,
    CONF_DASHBOARD_WIN_INDEX,
    DOMAIN,
)
from custom_components.minitel_interface.dashboard.orchestrator import async_update_dashboard


def _make_entry(hass, entry_id: str, *, options: dict, switch_on: bool = True):
    entry = SimpleNamespace(entry_id=entry_id, options=options)
    client = AsyncMock()
    coordinator = SimpleNamespace(client=client)
    switch = SimpleNamespace(is_on=switch_on)
    hass.data.setdefault(DOMAIN, {})[entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "dashboard_switch": switch,
    }
    return entry, coordinator, switch


_BASE_OPTIONS = {
    CONF_DASHBOARD_WEATHER_ENTITY: "weather.home",
    CONF_DASHBOARD_WIN_INDEX: 0,
    CONF_DASHBOARD_OBJ_INDEX: 0,
    CONF_DASHBOARD_POS_X: 0,
    CONF_DASHBOARD_POS_Y: 0,
    CONF_DASHBOARD_WIDTH: 200,
    CONF_DASHBOARD_HEIGHT: 100,
}


async def test_orchestrator_skips_when_switch_off(hass):
    entry, coordinator, _switch = _make_entry(hass, "entry1", options=_BASE_OPTIONS, switch_on=False)

    await async_update_dashboard(hass, entry, coordinator)

    coordinator.client.async_set_object_picture.assert_not_awaited()


async def test_orchestrator_skips_when_not_configured(hass):
    entry, coordinator, _switch = _make_entry(hass, "entry2", options={})

    await async_update_dashboard(hass, entry, coordinator)

    coordinator.client.async_set_object_picture.assert_not_awaited()


async def test_orchestrator_pushes_clock_weather_when_no_media_player(hass):
    hass.states.async_set("weather.home", "sunny", {"temperature": 21.5, "temperature_unit": "°C"})
    entry, coordinator, _switch = _make_entry(hass, "entry3", options=_BASE_OPTIONS)

    await async_update_dashboard(hass, entry, coordinator)

    coordinator.client.async_set_object_picture.assert_awaited_once()
    args, kwargs = coordinator.client.async_set_object_picture.call_args
    assert args[:6] == (0, 0, 0, 0, 200, 100)
    assert kwargs["is_png"] is True
    assert args[6].startswith(b"\x89PNG\r\n\x1a\n")
