"""Tests for Minitel Interface services."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.minitel_interface.const import CONF_HOST, CONF_PORT, DOMAIN


@pytest.fixture
async def mock_client():
    with patch("custom_components.minitel_interface.WmClient") as mock_client_cls:
        client = AsyncMock()
        client.async_get_summary.return_value = []
        client.connected = True
        mock_client_cls.return_value = client
        yield client


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_client):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.76", CONF_PORT: 1710})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_win_create_service(hass: HomeAssistant, setup_integration, mock_client) -> None:
    assert hass.services.has_service(DOMAIN, "win_create")

    await hass.services.async_call(
        DOMAIN,
        "win_create",
        {"pos_x": 0, "pos_y": 0, "width": 100, "height": 100, "background_color": 5},
        blocking=True,
    )

    mock_client.async_win_create.assert_awaited_once_with(0, 0, 100, 100, 5)


async def test_win_destroy_service(hass: HomeAssistant, setup_integration, mock_client) -> None:
    await hass.services.async_call(DOMAIN, "win_destroy", {"win_index": 2}, blocking=True)
    mock_client.async_win_destroy.assert_awaited_once_with(2)


async def test_set_object_text_service(hass: HomeAssistant, setup_integration, mock_client) -> None:
    await hass.services.async_call(
        DOMAIN,
        "set_object_text",
        {
            "win_index": 0,
            "obj_index": 0,
            "x": 0,
            "y": 0,
            "width": 100,
            "height": 20,
            "font_size": 8,
            "text": "hello",
        },
        blocking=True,
    )
    mock_client.async_set_object_text.assert_awaited_once_with(0, 0, 0, 0, 100, 20, 8, "hello")


async def test_services_removed_on_unload(hass: HomeAssistant, setup_integration) -> None:
    assert hass.services.has_service(DOMAIN, "win_create")

    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "win_create")
