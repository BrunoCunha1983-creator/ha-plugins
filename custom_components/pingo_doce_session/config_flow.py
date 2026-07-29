from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_SHARED_PATH, DEFAULT_SHARED_PATH, DOMAIN


class PingoDoceSessionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Pingo Doce",
                data={CONF_SHARED_PATH: user_input[CONF_SHARED_PATH]},
            )

        schema = vol.Schema(
            {vol.Required(CONF_SHARED_PATH, default=DEFAULT_SHARED_PATH): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PingoDoceSessionOptionsFlow(config_entry)


class PingoDoceSessionOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_SHARED_PATH,
            self.config_entry.data.get(CONF_SHARED_PATH, DEFAULT_SHARED_PATH),
        )
        schema = vol.Schema({vol.Required(CONF_SHARED_PATH, default=current): str})
        return self.async_show_form(step_id="init", data_schema=schema)
