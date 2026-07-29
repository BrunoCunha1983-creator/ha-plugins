from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE_URL = "https://www.pingodoce.pt"
ACCOUNT_URL = f"{BASE_URL}/home/area-pessoal?menu=orders"
COUPONS_URL = f"{BASE_URL}/home/area-pessoal?menu=coupons"
BALANCE_URL = (
    f"{BASE_URL}/on/demandware.store/"
    "Sites-pingo-doce-Site/default/BPData-Info"
)
OPTIONS_FILE = Path("/data/options.json")
PROFILE_DIR = Path("/data/chromium-profile")
SESSION_DIR = Path("/data/session")
STORAGE_STATE_FILE = SESSION_DIR / "storage_state.json"
STATE_MEMORY_FILE = SESSION_DIR / "last_state.json"
SHARED_DIR = Path("/homeassistant/pingo_doce_plus")
STATE_FILE = SHARED_DIR / "state.json"
COMMAND_FILE = SHARED_DIR / "command.json"
COMMAND_RESULT_FILE = SHARED_DIR / "command_result.json"

DEFAULT_KEYWORDS = (
    "pedido",
    "compras",
    "preparação",
    "caminho",
    "entregue",
    "cancelada",
)


@dataclass(slots=True)
class Options:
    refresh_interval: int = 180
    watchdog_interval: int = 30
    log_level: str = "info"


def load_options() -> Options:
    try:
        raw = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}

    refresh = max(60, int(raw.get("refresh_interval", 180)))
    watchdog = max(10, int(raw.get("watchdog_interval", 30)))
    level = str(raw.get("log_level", "info")).lower()
    if level not in {"debug", "info", "warning", "error"}:
        level = "info"
    return Options(refresh, watchdog, level)


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def parse_pt_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9,.-]", "", str(value).strip())
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def compact_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def atomic_write_json(path: Path, data: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.chmod(mode)
    temporary.replace(path)


def load_previous_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_MEMORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
