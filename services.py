"""Service handlers for the Minitel Interface integration.

Windows and objects are created dynamically by the user, so this
integration exposes generic low-level actions mirroring the wm-server
protocol rather than per-window entities. Note that win_index/obj_index
are positions in server-side lists and shift when windows/objects are
destroyed (see WindowList::remove in light-wm) -- callers should re-check
the coordinator's data before acting on a stale index.
"""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_BACKGROUND_COLOR,
    ATTR_FILE_PATH,
    ATTR_FONT_SIZE,
    ATTR_FULLSCREEN,
    ATTR_HEIGHT,
    ATTR_OBJ_INDEX,
    ATTR_ORDER,
    ATTR_POS_X,
    ATTR_POS_Y,
    ATTR_TEXT,
    ATTR_WIDTH,
    ATTR_WIN_INDEX,
    ATTR_X,
    ATTR_Y,
    DOMAIN,
    MAX_PAYLOAD_BYTES,
    SERVICE_RM_OBJECT,
    SERVICE_SET_OBJECT_PICTURE,
    SERVICE_SET_OBJECT_TEXT,
    SERVICE_SET_OBJECT_VIDEO,
    SERVICE_WIN_CREATE,
    SERVICE_WIN_DESTROY,
    SERVICE_WIN_ORDER,
    SERVICE_WIN_TRANSFORM,
)
from .coordinator import MinitelCoordinator

_LOGGER = logging.getLogger(__name__)

_WIN_CREATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_POS_X): cv.positive_int,
        vol.Required(ATTR_POS_Y): cv.positive_int,
        vol.Required(ATTR_WIDTH): cv.positive_int,
        vol.Required(ATTR_HEIGHT): cv.positive_int,
        vol.Optional(ATTR_BACKGROUND_COLOR, default=0): vol.All(int, vol.Range(min=0, max=255)),
    }
)

_WIN_DESTROY_SCHEMA = vol.Schema({vol.Required(ATTR_WIN_INDEX): cv.positive_int})

_WIN_TRANSFORM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_WIN_INDEX): cv.positive_int,
        vol.Required(ATTR_POS_X): cv.positive_int,
        vol.Required(ATTR_POS_Y): cv.positive_int,
        vol.Required(ATTR_WIDTH): cv.positive_int,
        vol.Required(ATTR_HEIGHT): cv.positive_int,
    }
)

_WIN_ORDER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_WIN_INDEX): cv.positive_int,
        vol.Required(ATTR_ORDER): cv.positive_int,
    }
)

_OBJ_SET_BASE = {
    vol.Required(ATTR_WIN_INDEX): cv.positive_int,
    vol.Required(ATTR_OBJ_INDEX): cv.positive_int,
    vol.Required(ATTR_X): cv.positive_int,
    vol.Required(ATTR_Y): cv.positive_int,
    vol.Required(ATTR_WIDTH): cv.positive_int,
    vol.Required(ATTR_HEIGHT): cv.positive_int,
}

_SET_OBJECT_TEXT_SCHEMA = vol.Schema(
    {
        **_OBJ_SET_BASE,
        vol.Optional(ATTR_FONT_SIZE, default=8): cv.positive_int,
        vol.Required(ATTR_TEXT): cv.string,
    }
)

_SET_OBJECT_PICTURE_SCHEMA = vol.Schema({**_OBJ_SET_BASE, vol.Required(ATTR_FILE_PATH): cv.string})

_SET_OBJECT_VIDEO_SCHEMA = vol.Schema(
    {
        **_OBJ_SET_BASE,
        vol.Required(ATTR_FILE_PATH): cv.string,
        vol.Optional(ATTR_FULLSCREEN, default=False): cv.boolean,
    }
)

_RM_OBJECT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_WIN_INDEX): cv.positive_int,
        vol.Required(ATTR_OBJ_INDEX): cv.positive_int,
    }
)


def _get_coordinator(hass: HomeAssistant) -> MinitelCoordinator:
    """Return the (single) coordinator for this integration."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise HomeAssistantError("Minitel Interface is not set up")
    return next(iter(entries.values()))["coordinator"]


async def _async_read_media_file(hass: HomeAssistant, file_path: str) -> bytes:
    """Read a media file from disk, respecting HA's allowed-paths policy."""
    if not hass.config.is_allowed_path(file_path):
        raise HomeAssistantError(f"'{file_path}' is not an allowed path")

    def _read() -> bytes:
        data = Path(file_path).read_bytes()
        if len(data) > MAX_PAYLOAD_BYTES:
            raise HomeAssistantError(
                f"'{file_path}' is {len(data)} bytes, exceeds the {MAX_PAYLOAD_BYTES}-byte limit"
            )
        return data

    return await hass.async_add_executor_job(_read)


def _is_png(file_path: str) -> bool:
    return Path(file_path).suffix.lower() == ".png"


def async_register_services(hass: HomeAssistant) -> None:
    """Register all Minitel Interface services (once, at domain level)."""

    async def async_win_create(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.client.async_win_create(
            call.data[ATTR_POS_X],
            call.data[ATTR_POS_Y],
            call.data[ATTR_WIDTH],
            call.data[ATTR_HEIGHT],
            call.data[ATTR_BACKGROUND_COLOR],
        )
        await coordinator.async_request_refresh()

    async def async_win_destroy(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.client.async_win_destroy(call.data[ATTR_WIN_INDEX])
        await coordinator.async_request_refresh()

    async def async_win_transform(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.client.async_win_transform(
            call.data[ATTR_WIN_INDEX],
            call.data[ATTR_POS_X],
            call.data[ATTR_POS_Y],
            call.data[ATTR_WIDTH],
            call.data[ATTR_HEIGHT],
        )
        await coordinator.async_request_refresh()

    async def async_win_order(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.client.async_win_order(call.data[ATTR_WIN_INDEX], call.data[ATTR_ORDER])
        await coordinator.async_request_refresh()

    async def async_set_object_text(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.client.async_set_object_text(
            call.data[ATTR_WIN_INDEX],
            call.data[ATTR_OBJ_INDEX],
            call.data[ATTR_X],
            call.data[ATTR_Y],
            call.data[ATTR_WIDTH],
            call.data[ATTR_HEIGHT],
            call.data[ATTR_FONT_SIZE],
            call.data[ATTR_TEXT],
        )
        await coordinator.async_request_refresh()

    async def async_set_object_picture(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        file_path = call.data[ATTR_FILE_PATH]
        image_bytes = await _async_read_media_file(hass, file_path)
        await coordinator.client.async_set_object_picture(
            call.data[ATTR_WIN_INDEX],
            call.data[ATTR_OBJ_INDEX],
            call.data[ATTR_X],
            call.data[ATTR_Y],
            call.data[ATTR_WIDTH],
            call.data[ATTR_HEIGHT],
            image_bytes,
            is_png=_is_png(file_path),
        )
        await coordinator.async_request_refresh()

    async def async_set_object_video(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        video_bytes = await _async_read_media_file(hass, call.data[ATTR_FILE_PATH])
        await coordinator.client.async_set_object_video(
            call.data[ATTR_WIN_INDEX],
            call.data[ATTR_OBJ_INDEX],
            call.data[ATTR_X],
            call.data[ATTR_Y],
            call.data[ATTR_WIDTH],
            call.data[ATTR_HEIGHT],
            video_bytes,
            fullscreen=call.data[ATTR_FULLSCREEN],
        )
        await coordinator.async_request_refresh()

    async def async_rm_object(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.client.async_rm_object(call.data[ATTR_WIN_INDEX], call.data[ATTR_OBJ_INDEX])
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVICE_WIN_CREATE, async_win_create, schema=_WIN_CREATE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_WIN_DESTROY, async_win_destroy, schema=_WIN_DESTROY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_WIN_TRANSFORM, async_win_transform, schema=_WIN_TRANSFORM_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_WIN_ORDER, async_win_order, schema=_WIN_ORDER_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_OBJECT_TEXT, async_set_object_text, schema=_SET_OBJECT_TEXT_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_OBJECT_PICTURE, async_set_object_picture, schema=_SET_OBJECT_PICTURE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_OBJECT_VIDEO, async_set_object_video, schema=_SET_OBJECT_VIDEO_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RM_OBJECT, async_rm_object, schema=_RM_OBJECT_SCHEMA)


def async_unregister_services(hass: HomeAssistant) -> None:
    """Remove all Minitel Interface services (called when the last entry unloads)."""
    for service in (
        SERVICE_WIN_CREATE,
        SERVICE_WIN_DESTROY,
        SERVICE_WIN_TRANSFORM,
        SERVICE_WIN_ORDER,
        SERVICE_SET_OBJECT_TEXT,
        SERVICE_SET_OBJECT_PICTURE,
        SERVICE_SET_OBJECT_VIDEO,
        SERVICE_RM_OBJECT,
    ):
        hass.services.async_remove(DOMAIN, service)
