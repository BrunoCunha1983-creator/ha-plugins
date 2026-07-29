from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    EVENT_LOGIN_REQUIRED,
    EVENT_ORDER_CHANGED,
    EVENT_WEBSITE_CHANGED,
    PLATFORMS,
)
from .coordinator import PingoDocePlusCoordinator

SERVICE_REFRESH = "refresh"
SERVICE_OPEN_LOGIN = "open_login"
SERVICE_RESTART_BROWSER = "restart_browser"


def _coordinator(hass: HomeAssistant) -> PingoDocePlusCoordinator:
    entries = hass.data.get(DOMAIN, {})
    for coordinator in entries.values():
        return coordinator
    raise HomeAssistantError("A integração Pingo Doce Plus não está configurada")


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    hass.data.setdefault(DOMAIN, {})

    async def async_command(call: ServiceCall) -> None:
        await _coordinator(hass).async_send_command(call.service)

    for service in (SERVICE_REFRESH, SERVICE_OPEN_LOGIN, SERVICE_RESTART_BROWSER):
        hass.services.async_register(DOMAIN, service, async_command)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = PingoDocePlusCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    previous = dict(coordinator.data)

    @callback
    def _handle_update() -> None:
        nonlocal previous
        current = dict(coordinator.data)
        previous_order = previous.get("current_order") or {}
        current_order = current.get("current_order") or {}

        if (
            previous_order.get("number") != current_order.get("number")
            or previous_order.get("status") != current_order.get("status")
        ):
            hass.bus.async_fire(
                EVENT_ORDER_CHANGED,
                {
                    "previous_number": previous_order.get("number"),
                    "previous_status": previous_order.get("status"),
                    "number": current_order.get("number"),
                    "status": current_order.get("status"),
                    "progress": current_order.get("progress"),
                },
            )

        if current.get("website_changed") and not previous.get("website_changed"):
            hass.bus.async_fire(
                EVENT_WEBSITE_CHANGED,
                {
                    "order_number": current_order.get("number"),
                    "order_status": current_order.get("status"),
                },
            )

        if (
            current.get("status") == "login_required"
            and previous.get("status") != "login_required"
        ):
            hass.bus.async_fire(EVENT_LOGIN_REQUIRED, {})

        previous = current

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
