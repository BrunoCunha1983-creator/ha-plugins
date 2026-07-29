from __future__ import annotations

from pathlib import Path

from homeassistant.const import Platform

DOMAIN = "pingo_doce_session"
NAME = "Pingo Doce Session"
DEFAULT_SHARED_PATH = "/config/pingo_doce_session"
CONF_SHARED_PATH = "shared_path"
UPDATE_INTERVAL_SECONDS = 15

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.BUTTON,
]

STATE_FILENAME = "state.json"
COOKIE_HEADER_FILENAME = "cookie_header.txt"
COOKIES_JSON_FILENAME = "cookies.json"
COMMAND_FILENAME = "command.json"
COMMAND_RESULT_FILENAME = "command_result.json"


def shared_file(shared_path: str, filename: str) -> Path:
    return Path(shared_path) / filename
