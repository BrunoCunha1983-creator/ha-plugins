from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PingoDocePlusCoordinator
from .entity import PingoDocePlusEntity


@dataclass(frozen=True, kw_only=True)
class PingoDocePlusSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


def nested(data: dict[str, Any], section: str, key: str) -> Any:
    value = data.get(section)
    return value.get(key) if isinstance(value, dict) else None


def timestamp(data: dict[str, Any], key: str) -> datetime | None:
    value = data.get(key)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


SENSORS = (
    PingoDocePlusSensorDescription(
        key="status", translation_key="status", icon="mdi:account-key",
        value_fn=lambda data: data.get("status"),
    ),
    PingoDocePlusSensorDescription(
        key="points", translation_key="points", icon="mdi:star-circle",
        native_unit_of_measurement="pontos", value_fn=lambda data: data.get("points"),
    ),
    PingoDocePlusSensorDescription(
        key="balance", translation_key="balance", icon="mdi:cash-multiple",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        value_fn=lambda data: data.get("balance"),
    ),
    PingoDocePlusSensorDescription(
        key="expiry_amount", translation_key="expiry_amount", icon="mdi:cash-clock",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        value_fn=lambda data: data.get("expiry_amount"),
    ),
    PingoDocePlusSensorDescription(
        key="expiry_date", translation_key="expiry_date", icon="mdi:calendar-clock",
        value_fn=lambda data: data.get("expiry_date"),
    ),
    PingoDocePlusSensorDescription(
        key="expiry_message", translation_key="expiry_message", icon="mdi:message-alert",
        value_fn=lambda data: data.get("expiry_message"),
    ),
    PingoDocePlusSensorDescription(
        key="active_orders", translation_key="active_orders", icon="mdi:cart-clock",
        native_unit_of_measurement="encomendas",
        value_fn=lambda data: data.get("active_orders"),
    ),
    PingoDocePlusSensorDescription(
        key="current_order_number", translation_key="current_order_number", icon="mdi:package-variant",
        value_fn=lambda data: nested(data, "current_order", "number"),
    ),
    PingoDocePlusSensorDescription(
        key="current_order_status", translation_key="current_order_status", icon="mdi:truck-delivery",
        value_fn=lambda data: nested(data, "current_order", "status"),
    ),
    PingoDocePlusSensorDescription(
        key="current_order_delivery_window", translation_key="current_order_delivery_window", icon="mdi:calendar-range",
        value_fn=lambda data: nested(data, "current_order", "delivery_window"),
    ),
    PingoDocePlusSensorDescription(
        key="current_order_progress", translation_key="current_order_progress", icon="mdi:progress-clock",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: nested(data, "current_order", "progress"),
    ),
    PingoDocePlusSensorDescription(
        key="last_order_number", translation_key="last_order_number", icon="mdi:package-check",
        value_fn=lambda data: nested(data, "last_order", "number"),
    ),
    PingoDocePlusSensorDescription(
        key="last_order_status", translation_key="last_order_status", icon="mdi:history",
        value_fn=lambda data: nested(data, "last_order", "status_date"),
    ),
    PingoDocePlusSensorDescription(
        key="last_order_total", translation_key="last_order_total", icon="mdi:cash-register",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        value_fn=lambda data: nested(data, "last_order", "total"),
    ),
    PingoDocePlusSensorDescription(
        key="purchase_history_count", translation_key="purchase_history_count", icon="mdi:history",
        native_unit_of_measurement="encomendas",
        value_fn=lambda data: data.get("purchase_history_count"),
    ),
    PingoDocePlusSensorDescription(
        key="coupon_count", translation_key="coupon_count", icon="mdi:ticket-percent",
        native_unit_of_measurement="cupões",
        value_fn=lambda data: data.get("coupon_count"),
    ),
    PingoDocePlusSensorDescription(
        key="active_coupon_count", translation_key="active_coupon_count", icon="mdi:ticket-confirmation",
        native_unit_of_measurement="cupões",
        value_fn=lambda data: data.get("active_coupon_count"),
    ),
    PingoDocePlusSensorDescription(
        key="detected_words", translation_key="detected_words", icon="mdi:text-search",
        value_fn=lambda data: ", ".join(data.get("detected_words", [])) or None,
    ),
    PingoDocePlusSensorDescription(
        key="session_expiry", translation_key="session_expiry", icon="mdi:timer-lock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: timestamp(data, "session_expiry"),
    ),
    PingoDocePlusSensorDescription(
        key="last_update", translation_key="last_update", icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: timestamp(data, "last_update"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: PingoDocePlusCoordinator = entry.runtime_data
    async_add_entities(PingoDocePlusSensor(coordinator, item) for item in SENSORS)


class PingoDocePlusSensor(PingoDocePlusEntity, SensorEntity):
    entity_description: PingoDocePlusSensorDescription

    def __init__(
        self,
        coordinator: PingoDocePlusCoordinator,
        description: PingoDocePlusSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        key = self.entity_description.key
        data = self.coordinator.data
        if key == "status":
            return {
                "last_error": data.get("last_error"),
                "browser_url": data.get("browser_url"),
                "version": data.get("version"),
                "capabilities": data.get("capabilities"),
            }
        if key.startswith("current_order_") and isinstance(data.get("current_order"), dict):
            order = data["current_order"]
            return {
                "summary_status": order.get("summary_status"),
                "address": order.get("address"),
                "postal_code": order.get("postal_code"),
                "detail_url": order.get("detail_url"),
                "steps": order.get("steps"),
            }
        if key.startswith("last_order_"):
            return {"history": data.get("history", [])[:10]}
        if key in {"coupon_count", "active_coupon_count"}:
            return {"coupons": data.get("coupons", [])[:20]}
        return None
