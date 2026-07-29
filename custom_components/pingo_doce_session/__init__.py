from __future__ import annotations

import json
from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .const import (
    COOKIES_JSON_FILENAME,
    COOKIE_HEADER_FILENAME,
    DOMAIN,
    PLATFORMS,
    shared_file,
)
from .coordinator import PingoDoceSessionCoordinator

SERVICE_GET_COOKIE = "get_cookie"
SERVICE_REFRESH = "refresh"
SERVICE_EXPORT_COOKIES = "export_cookies"


def _first_coordinator(hass: HomeAssistant) -> PingoDoceSessionCoordinator:
    entries = hass.data.get(DOMAIN, {})
    for coordinator in entries.values():
        return coordinator
    raise HomeAssistantError("A integração Pingo Doce Session não está configurada")


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    hass.data.setdefault(DOMAIN, {})

    async def async_command(call: ServiceCall) -> None:
        coordinator = _first_coordinator(hass)
        await coordinator.async_send_command(call.service)

    async def async_get_cookie(call: ServiceCall) -> dict[str, Any]:
        coordinator = _first_coordinator(hass)
        await coordinator.async_send_command("export_cookies")
        header_path = shared_file(coordinator.shared_path, COOKIE_HEADER_FILENAME)
        json_path = shared_file(coordinator.shared_path, COOKIES_JSON_FILENAME)
        try:
            cookie_header = await hass.async_add_executor_job(header_path.read_text, "utf-8")
            cookies_text = await hass.async_add_executor_job(json_path.read_text, "utf-8")
            cookies = json.loads(cookies_text)
        except (OSError, json.JSONDecodeError) as err:
            raise HomeAssistantError(f"Não foi possível obter os cookies: {err}") from err

        response = {"cookie_header": cookie_header, "cookies": cookies}
        if call.data.get("show_notification", False):
            persistent_notification.async_create(
                hass,
                f"```text\n{cookie_header}\n```",
                title="Cookie Pingo Doce",
                notification_id="pingo_doce_session_cookie",
            )
        return response

    for service in (SERVICE_REFRESH, SERVICE_EXPORT_COOKIES):
        hass.services.async_register(DOMAIN, service, async_command)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_COOKIE,
        async_get_cookie,
        schema=vol.Schema({vol.Optional("show_notification", default=False): bool}),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = PingoDoceSessionCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
