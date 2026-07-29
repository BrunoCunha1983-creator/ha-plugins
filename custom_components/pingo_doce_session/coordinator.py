from __future__ import annotations

import asyncio
import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_FILENAME,
    COMMAND_RESULT_FILENAME,
    CONF_SHARED_PATH,
    DEFAULT_SHARED_PATH,
    DOMAIN,
    STATE_FILENAME,
    UPDATE_INTERVAL_SECONDS,
    shared_file,
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class PingoDoceSessionCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.shared_path = str(
            entry.options.get(
                CONF_SHARED_PATH,
                entry.data.get(CONF_SHARED_PATH, DEFAULT_SHARED_PATH),
            )
        )
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        path = shared_file(self.shared_path, STATE_FILENAME)
        try:
            return await self.hass.async_add_executor_job(_read_json, path)
        except FileNotFoundError as err:
            raise UpdateFailed(
                "O ficheiro do add-on ainda não existe. Inicie ou atualize o add-on Pingo Doce."
            ) from err
        except (OSError, json.JSONDecodeError) as err:
            raise UpdateFailed(f"Não foi possível ler o estado do add-on: {err}") from err

    async def async_send_command(
        self,
        command: str,
        *,
        wait_result: bool = True,
        timeout: float = 75.0,
    ) -> dict[str, Any] | None:
        command_id = uuid.uuid4().hex
        payload = {"id": command_id, "command": command}
        command_path = shared_file(self.shared_path, COMMAND_FILENAME)
        result_path = shared_file(self.shared_path, COMMAND_RESULT_FILENAME)
        await self.hass.async_add_executor_job(_write_json_atomic, command_path, payload)

        if not wait_result:
            return None

        async with asyncio.timeout(timeout):
            while True:
                await asyncio.sleep(0.5)
                try:
                    result = await self.hass.async_add_executor_job(_read_json, result_path)
                except (FileNotFoundError, OSError, json.JSONDecodeError):
                    continue
                if result.get("id") != command_id:
                    continue
                if not result.get("success"):
                    raise UpdateFailed(str(result.get("error") or "O comando falhou"))
                await self.async_request_refresh()
                return result
