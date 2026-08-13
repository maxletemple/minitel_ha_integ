"""Tests for dashboard.orchestrator: switch gating and scene fallback wiring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.minitel_interface.const import (
    CONF_DASHBOARD_HEIGHT,
    CONF_DASHBOARD_MEDIA_PLAYER_ENTITY,
    CONF_DASHBOARD_OBJ_INDEX,
    CONF_DASHBOARD_POS_X,
    CONF_DASHBOARD_POS_Y,
    CONF_DASHBOARD_WEATHER_ENTITY,
    CONF_DASHBOARD_WIDTH,
    CONF_DASHBOARD_WIN_INDEX,
    DOMAIN,
)
from custom_components.minitel_interface.dashboard.orchestrator import (
    async_ensure_dashboard_window,
    async_track_media_player_changes,
    async_update_dashboard,
)


def _make_entry(hass, entry_id: str, *, options: dict, switch_on: bool = True, windows: list | None = None):
    entry = SimpleNamespace(entry_id=entry_id, options=options)
    client = AsyncMock()
    coordinator = SimpleNamespace(client=client, data=windows or [], async_request_refresh=AsyncMock())
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


async def test_ensure_window_creates_when_none_exist(hass):
    entry, coordinator, _switch = _make_entry(hass, "entry7", options=_BASE_OPTIONS, windows=[])

    await async_ensure_dashboard_window(hass, entry, coordinator.client, coordinator)

    coordinator.client.async_win_create.assert_awaited_once_with(0, 0, 200, 100)
    coordinator.async_request_refresh.assert_awaited_once()


async def test_ensure_window_skips_when_windows_already_exist(hass):
    entry, coordinator, _switch = _make_entry(hass, "entry8", options=_BASE_OPTIONS, windows=[object()])

    await async_ensure_dashboard_window(hass, entry, coordinator.client, coordinator)

    coordinator.client.async_win_create.assert_not_awaited()


async def test_ensure_window_skips_when_not_configured(hass):
    entry, coordinator, _switch = _make_entry(hass, "entry9", options={}, windows=[])

    await async_ensure_dashboard_window(hass, entry, coordinator.client, coordinator)

    coordinator.client.async_win_create.assert_not_awaited()


async def test_ensure_window_skips_when_win_index_not_zero(hass):
    options = {**_BASE_OPTIONS, CONF_DASHBOARD_WIN_INDEX: 1}
    entry, coordinator, _switch = _make_entry(hass, "entry10", options=options, windows=[])

    await async_ensure_dashboard_window(hass, entry, coordinator.client, coordinator)

    coordinator.client.async_win_create.assert_not_awaited()


def test_track_media_player_changes_returns_none_when_not_configured(hass):
    entry, coordinator, _switch = _make_entry(hass, "entry4", options=_BASE_OPTIONS)

    assert async_track_media_player_changes(hass, entry, coordinator) is None


async def test_track_media_player_changes_triggers_on_relevant_change(hass):
    options = {**_BASE_OPTIONS, CONF_DASHBOARD_MEDIA_PLAYER_ENTITY: "media_player.appletv"}
    entry, coordinator, _switch = _make_entry(hass, "entry5", options=options)
    hass.states.async_set("media_player.appletv", "idle", {})

    remove = async_track_media_player_changes(hass, entry, coordinator)
    assert remove is not None
    try:
        hass.states.async_set("media_player.appletv", "playing", {"media_title": "Show"})
        await hass.async_block_till_done()
        coordinator.client.async_set_object_picture.assert_awaited()
    finally:
        remove()


async def test_track_media_player_changes_ignores_irrelevant_change(hass):
    options = {**_BASE_OPTIONS, CONF_DASHBOARD_MEDIA_PLAYER_ENTITY: "media_player.appletv"}
    entry, coordinator, _switch = _make_entry(hass, "entry6", options=options)
    hass.states.async_set("media_player.appletv", "playing", {"media_title": "Show", "media_position": 10})

    remove = async_track_media_player_changes(hass, entry, coordinator)
    try:
        # Only media_position changes (e.g. playback progress ticking) - not
        # one of the fields that affects what's rendered.
        hass.states.async_set("media_player.appletv", "playing", {"media_title": "Show", "media_position": 20})
        await hass.async_block_till_done()
        coordinator.client.async_set_object_picture.assert_not_awaited()
    finally:
        remove()
