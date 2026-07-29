from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PingoDocePlusCoordinator
from .entity import PingoDocePlusEntity

BINARY_SENSORS = (
    BinarySensorEntityDescription(
        key="authenticated",
        translation_key="authenticated",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:account-check",
    ),
    BinarySensorEntityDescription(
        key="browser_running",
        translation_key="browser_running",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:web",
    ),
    BinarySensorEntityDescription(
        key="active_order",
        translation_key="active_order",
        icon="mdi:cart-clock",
    ),
    BinarySensorEntityDescription(
        key="website_changed",
        translation_key="website_changed",
        icon="mdi:web-sync",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: PingoDocePlusCoordinator = entry.runtime_data
    async_add_entities(PingoDocePlusBinarySensor(coordinator, item) for item in BINARY_SENSORS)


class PingoDocePlusBinarySensor(PingoDocePlusEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: PingoDocePlusCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        key = self.entity_description.key
        if key == "active_order":
            return bool(self.coordinator.data.get("active_orders", 0))
        return bool(self.coordinator.data.get(key))
