from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PingoDoceSessionCoordinator
from .entity import PingoDoceSessionEntity


@dataclass(frozen=True, kw_only=True)
class PingoDoceSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


def _timestamp(data: dict[str, Any]) -> datetime | None:
    value = data.get("last_update")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


SENSORS: tuple[PingoDoceSensorDescription, ...] = (
    PingoDoceSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:account-key",
        value_fn=lambda data: data.get("status"),
    ),
    PingoDoceSensorDescription(
        key="points",
        translation_key="points",
        native_unit_of_measurement="pontos",
        icon="mdi:star-circle",
        value_fn=lambda data: data.get("points"),
    ),
    PingoDoceSensorDescription(
        key="balance",
        translation_key="balance",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:cash-multiple",
        value_fn=lambda data: data.get("balance"),
    ),
    PingoDoceSensorDescription(
        key="expiry_amount",
        translation_key="expiry_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        icon="mdi:cash-clock",
        value_fn=lambda data: data.get("expiry_amount"),
    ),
    PingoDoceSensorDescription(
        key="expiry_date",
        translation_key="expiry_date",
        icon="mdi:calendar-clock",
        value_fn=lambda data: data.get("expiry_date"),
    ),
    PingoDoceSensorDescription(
        key="expiry_message",
        translation_key="expiry_message",
        icon="mdi:message-alert",
        value_fn=lambda data: data.get("expiry_message"),
    ),
    PingoDoceSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:update",
        value_fn=_timestamp,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: PingoDoceSessionCoordinator = entry.runtime_data
    async_add_entities(PingoDoceSensor(coordinator, description) for description in SENSORS)


class PingoDoceSensor(PingoDoceSessionEntity, SensorEntity):
    entity_description: PingoDoceSensorDescription

    def __init__(
        self,
        coordinator: PingoDoceSessionCoordinator,
        description: PingoDoceSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "status":
            return None
        return {
            "last_error": self.coordinator.data.get("last_error"),
            "browser_url": self.coordinator.data.get("browser_url"),
            "addon_version": self.coordinator.data.get("addon_version"),
        }
