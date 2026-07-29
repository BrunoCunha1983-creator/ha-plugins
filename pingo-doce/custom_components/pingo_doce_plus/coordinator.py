import json
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, SHARED

class PingoDoceCoordinator(DataUpdateCoordinator):
    def __init__(self, hass):
        super().__init__(hass, logger=__import__('logging').getLogger(__name__), name=DOMAIN,
                         update_interval=timedelta(seconds=15))

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(
                lambda: json.loads((SHARED / 'state.json').read_text(encoding='utf-8'))
            )
        except FileNotFoundError as err:
            raise UpdateFailed('Inicie o add-on Pingo Doce Plus.') from err
        except (OSError, json.JSONDecodeError) as err:
            raise UpdateFailed(str(err)) from err
