"""Diagnostic sensors for the Minitel Interface integration.

Windows/objects are user-created and dynamic, so there is deliberately no
per-window entity here (unstable indices, unbounded cardinality). These
sensors only expose aggregate state useful for visibility in the UI.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_PORT, DOMAIN
from .coordinator import MinitelCoordinator

WINDOW_COUNT_DESCRIPTION = SensorEntityDescription(
    key="window_count",
    name="Window count",
    entity_category=EntityCategory.DIAGNOSTIC,
    state_class="measurement",
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MinitelCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([MinitelWindowCountSensor(coordinator, entry)])


class MinitelWindowCountSensor(CoordinatorEntity[MinitelCoordinator], SensorEntity):
    """Number of windows currently open on wm-server, per the last poll."""

    entity_description = WINDOW_COUNT_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: MinitelCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_window_count"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Minitel display server",
            configuration_url=f"tcp://{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        )

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, list[dict]]:
        windows = self.coordinator.data or []
        return {
            "windows": [
                {
                    "index": win.index,
                    "pos_x": win.pos_x,
                    "pos_y": win.pos_y,
                    "width": win.width,
                    "height": win.height,
                    "background_color": win.background_color,
                    "objects": [{"index": obj.index, "type": obj.data_type} for obj in win.objects],
                }
                for win in windows
            ]
        }
