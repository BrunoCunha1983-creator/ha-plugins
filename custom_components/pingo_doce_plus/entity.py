from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import PingoDocePlusCoordinator


class PingoDocePlusEntity(CoordinatorEntity[PingoDocePlusCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PingoDocePlusCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"pingo_doce_plus_{key}"
        version = str(coordinator.data.get("version", "unknown")) if coordinator.data else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name=NAME,
            manufacturer="Pingo Doce",
            model="Sessão persistente",
            sw_version=version,
        )
