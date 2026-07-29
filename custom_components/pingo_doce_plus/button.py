from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PingoDocePlusCoordinator
from .entity import PingoDocePlusEntity


@dataclass(frozen=True, kw_only=True)
class PingoDocePlusButtonDescription(ButtonEntityDescription):
    command: str


BUTTONS = (
    PingoDocePlusButtonDescription(
        key="refresh",
        translation_key="refresh",
        icon="mdi:refresh",
        command="refresh",
    ),
    PingoDocePlusButtonDescription(
        key="open_login",
        translation_key="open_login",
        icon="mdi:login",
        command="open_login",
    ),
    PingoDocePlusButtonDescription(
        key="restart_browser",
        translation_key="restart_browser",
        icon="mdi:restart",
        command="restart_browser",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: PingoDocePlusCoordinator = entry.runtime_data
    async_add_entities(PingoDocePlusButton(coordinator, item) for item in BUTTONS)


class PingoDocePlusButton(PingoDocePlusEntity, ButtonEntity):
    entity_description: PingoDocePlusButtonDescription

    def __init__(
        self,
        coordinator: PingoDocePlusCoordinator,
        description: PingoDocePlusButtonDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(self.entity_description.command)
