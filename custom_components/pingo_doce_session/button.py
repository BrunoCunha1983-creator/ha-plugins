from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import COOKIE_HEADER_FILENAME, shared_file
from .coordinator import PingoDoceSessionCoordinator
from .entity import PingoDoceSessionEntity


@dataclass(frozen=True, kw_only=True)
class CommandButtonDescription(ButtonEntityDescription):
    command: str


BUTTONS = (
    CommandButtonDescription(
        key="refresh",
        translation_key="refresh",
        icon="mdi:refresh",
        command="refresh",
    ),
    CommandButtonDescription(
        key="export_cookies",
        translation_key="export_cookies",
        icon="mdi:cookie-sync",
        command="export_cookies",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: PingoDoceSessionCoordinator = entry.runtime_data
    entities = [PingoDoceCommandButton(coordinator, description) for description in BUTTONS]
    entities.append(PingoDoceCopyCookieButton(coordinator))
    async_add_entities(entities)


class PingoDoceCommandButton(PingoDoceSessionEntity, ButtonEntity):
    entity_description: CommandButtonDescription

    def __init__(
        self,
        coordinator: PingoDoceSessionCoordinator,
        description: CommandButtonDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(self.entity_description.command)


class PingoDoceCopyCookieButton(PingoDoceSessionEntity, ButtonEntity):
    _attr_translation_key = "copy_cookie"
    _attr_icon = "mdi:content-copy"

    def __init__(self, coordinator: PingoDoceSessionCoordinator) -> None:
        super().__init__(coordinator, "copy_cookie")

    async def async_press(self) -> None:
        await self.coordinator.async_send_command("export_cookies")
        path = shared_file(self.coordinator.shared_path, COOKIE_HEADER_FILENAME)
        cookie = await self.hass.async_add_executor_job(path.read_text, "utf-8")
        persistent_notification.async_create(
            self.hass,
            f"```text\n{cookie}\n```",
            title="Cookie Pingo Doce",
            notification_id="pingo_doce_session_cookie",
        )
