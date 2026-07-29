from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PingoDoceSessionCoordinator
from .entity import PingoDoceSessionEntity

BINARY_SENSORS = (
    BinarySensorEntityDescription(
        key="authenticated",
        translation_key="authenticated",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:account-check",
    ),
    BinarySensorEntityDescription(
        key="cookie_available",
        translation_key="cookie_available",
        icon="mdi:cookie-check",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: PingoDoceSessionCoordinator = entry.runtime_data
    async_add_entities(
        PingoDoceBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class PingoDoceBinarySensor(PingoDoceSessionEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: PingoDoceSessionCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get(self.entity_description.key))

    @property
    def extra_state_attributes(self):
        if self.entity_description.key != "cookie_available":
            return None
        return {"cookie_names": self.coordinator.data.get("cookie_names", [])}
