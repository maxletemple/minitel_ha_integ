"""Tests for the Minitel Interface config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.minitel_interface.const import CONF_HOST, CONF_PORT, DOMAIN
from custom_components.minitel_interface.wmclient import WmConnectionError

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    # Creating the entry via the flow also triggers HA to set it up, which
    # goes through __init__.WmClient, not config_flow.WmClient - patch both.
    with (
        patch("custom_components.minitel_interface.config_flow.WmClient") as mock_flow_client_cls,
        patch("custom_components.minitel_interface.WmClient") as mock_setup_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.async_get_summary.return_value = []
        mock_flow_client_cls.return_value = mock_client
        mock_setup_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.76", CONF_PORT: 1710}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.76:1710"
    assert result["data"] == {CONF_HOST: "192.168.1.76", CONF_PORT: 1710}
    mock_client.async_connect.assert_awaited()
    mock_client.async_get_summary.assert_awaited()


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.minitel_interface.config_flow.WmClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.async_connect.side_effect = WmConnectionError("boom")
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "192.168.1.76", CONF_PORT: 1710}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(hass: HomeAssistant) -> None:
    # manifest.json declares single_config_entry, so HA aborts the flow at
    # init time, before async_step_user (and thus WmClient) is ever reached.
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.76", CONF_PORT: 1710}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
