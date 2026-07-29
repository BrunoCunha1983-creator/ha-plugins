from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_FILENAME,
    COMMAND_RESULT_FILENAME,
    DOMAIN,
    STATE_FILENAME,
    UPDATE_INTERVAL_SECONDS,
    shared_file,
)

_LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


class PingoDocePlusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(_read_json, shared_file(STATE_FILENAME))
        except FileNotFoundError as err:
            raise UpdateFailed(
                "O add-on Pingo Doce Plus ainda não criou o estado. Inicie o add-on."
            ) from err
        except (OSError, json.JSONDecodeError) as err:
            raise UpdateFailed(f"Não foi possível ler o estado do add-on: {err}") from err

    async def async_send_command(
        self,
        command: str,
        *,
        wait_result: bool = True,
        timeout: float = 90.0,
    ) -> dict[str, Any] | None:
        command_id = uuid.uuid4().hex
        payload = {"id": command_id, "command": command}
        await self.hass.async_add_executor_job(
            _write_json_atomic, shared_file(COMMAND_FILENAME), payload
        )

        if not wait_result:
            return None

        async with asyncio.timeout(timeout):
            while True:
                await asyncio.sleep(0.5)
                try:
                    result = await self.hass.async_add_executor_job(
                        _read_json, shared_file(COMMAND_RESULT_FILENAME)
                    )
                except (FileNotFoundError, OSError, json.JSONDecodeError):
                    continue
                if result.get("id") != command_id:
                    continue
                if not result.get("success"):
                    raise UpdateFailed(str(result.get("error") or "O comando falhou"))
                await self.async_request_refresh()
                return result
