from __future__ import annotations

from pathlib import Path

from homeassistant.const import Platform

DOMAIN = "pingo_doce_plus"
NAME = "Pingo Doce Plus"
VERSION = "2.0.0"
DEFAULT_SHARED_PATH = "/config/pingo_doce_plus"
UPDATE_INTERVAL_SECONDS = 15

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
]

STATE_FILENAME = "state.json"
COMMAND_FILENAME = "command.json"
COMMAND_RESULT_FILENAME = "command_result.json"

EVENT_ORDER_CHANGED = "pingo_doce_plus_order_changed"
EVENT_WEBSITE_CHANGED = "pingo_doce_plus_website_changed"
EVENT_LOGIN_REQUIRED = "pingo_doce_plus_login_required"


def shared_file(filename: str) -> Path:
    return Path(DEFAULT_SHARED_PATH) / filename
