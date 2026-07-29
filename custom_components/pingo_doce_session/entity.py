from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PingoDoceSessionCoordinator


class PingoDoceSessionEntity(CoordinatorEntity[PingoDoceSessionCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PingoDoceSessionCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"pingo_doce_session_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "pingo_doce_session")},
            name="Pingo Doce",
            manufacturer="Pingo Doce",
            model="Sessão persistente",
            sw_version=str(coordinator.data.get("addon_version", "unknown"))
            if coordinator.data
            else None,
        )
