"""Config flow for the Minitel Interface integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DASHBOARD_HEIGHT,
    CONF_DASHBOARD_MEDIA_PLAYER_ENTITY,
    CONF_DASHBOARD_OBJ_INDEX,
    CONF_DASHBOARD_POS_X,
    CONF_DASHBOARD_POS_Y,
    CONF_DASHBOARD_WEATHER_ENTITY,
    CONF_DASHBOARD_WIDTH,
    CONF_DASHBOARD_WIN_INDEX,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .wmclient import WmClient, WmError
from .wmclient.const import DEFAULT_PORT

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


async def _async_validate_connection(host: str, port: int) -> None:
    """Raise WmError if the server is unreachable."""
    client = WmClient(host, port)
    try:
        await client.async_connect()
        await client.async_get_summary()
    finally:
        await client.async_close()


class MinitelInterfaceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minitel Interface."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _async_validate_connection(user_input[CONF_HOST], user_input[CONF_PORT])
            except WmError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    data=user_input,
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MinitelInterfaceOptionsFlow:
        return MinitelInterfaceOptionsFlow()


class MinitelInterfaceOptionsFlow(OptionsFlow):
    """Handle options (polling interval)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=2)),
                vol.Optional(
                    CONF_DASHBOARD_WEATHER_ENTITY,
                    description={"suggested_value": current.get(CONF_DASHBOARD_WEATHER_ENTITY)},
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
                vol.Optional(
                    CONF_DASHBOARD_MEDIA_PLAYER_ENTITY,
                    description={"suggested_value": current.get(CONF_DASHBOARD_MEDIA_PLAYER_ENTITY)},
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="media_player")),
                vol.Optional(
                    CONF_DASHBOARD_WIN_INDEX, default=current.get(CONF_DASHBOARD_WIN_INDEX, 0)
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONF_DASHBOARD_OBJ_INDEX, default=current.get(CONF_DASHBOARD_OBJ_INDEX, 0)
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONF_DASHBOARD_POS_X, default=current.get(CONF_DASHBOARD_POS_X, 0)
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONF_DASHBOARD_POS_Y, default=current.get(CONF_DASHBOARD_POS_Y, 0)
                ): vol.All(int, vol.Range(min=0)),
                vol.Optional(
                    CONF_DASHBOARD_WIDTH, default=current.get(CONF_DASHBOARD_WIDTH, 556)
                ): vol.All(int, vol.Range(min=1)),
                vol.Optional(
                    CONF_DASHBOARD_HEIGHT, default=current.get(CONF_DASHBOARD_HEIGHT, 512)
                ): vol.All(int, vol.Range(min=1)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
