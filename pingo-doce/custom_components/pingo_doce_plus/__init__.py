import json
import uuid
import voluptuous as vol
from homeassistant.components import persistent_notification
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, PLATFORMS, SHARED
from .coordinator import PingoDoceCoordinator

async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})

    async def command(call):
        payload = {'id': uuid.uuid4().hex, 'command': call.service}
        def write_command():
            SHARED.mkdir(parents=True, exist_ok=True)
            (SHARED / 'command.json').write_text(json.dumps(payload), encoding='utf-8')
        await hass.async_add_executor_job(write_command)

    async def get_cookie(call):
        try:
            cookie = await hass.async_add_executor_job(
                (SHARED / 'cookie_header.txt').read_text, 'utf-8'
            )
        except OSError as err:
            raise HomeAssistantError(f'Cookie indisponível: {err}') from err
        if call.data.get('show_notification', True):
            persistent_notification.async_create(
                hass, f'```text\n{cookie}\n```', title='Cookie Pingo Doce',
                notification_id='pingo_doce_plus_cookie')
        return {'cookie_header': cookie}

    for service in ('refresh', 'open_login', 'restart_browser', 'export_cookies'):
        hass.services.async_register(DOMAIN, service, command)
    hass.services.async_register(
        DOMAIN, 'get_cookie', get_cookie,
        schema=vol.Schema({vol.Optional('show_notification', default=True): bool}),
        supports_response=SupportsResponse.OPTIONAL)
    return True

async def async_setup_entry(hass, entry):
    coordinator = PingoDoceCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok
