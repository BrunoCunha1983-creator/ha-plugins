from __future__ import annotations

import asyncio
import json
import logging
import re
import signal
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

BASE_URL = "https://www.pingodoce.pt"
BALANCE_URL = (
    "https://www.pingodoce.pt/on/demandware.store/"
    "Sites-pingo-doce-Site/default/BPData-Info"
)
OPTIONS_FILE = Path("/data/options.json")
STORAGE_STATE_FILE = Path("/data/session/storage_state.json")
SHARED_DIR = Path("/config/pingo_doce_session")
STATE_FILE = SHARED_DIR / "state.json"
COOKIE_HEADER_FILE = SHARED_DIR / "cookie_header.txt"
COOKIES_JSON_FILE = SHARED_DIR / "cookies.json"
COMMAND_FILE = SHARED_DIR / "command.json"
COMMAND_RESULT_FILE = SHARED_DIR / "command_result.json"


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


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))


def load_refresh_interval() -> int:
    try:
        options = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        options = {}
    return max(60, int(options.get("refresh_interval", 300)))


class AddonBridge:
    def __init__(self) -> None:
        self.logger = logging.getLogger("pingo_doce_bridge")
        self.stop_event = asyncio.Event()
        self.refresh_interval = load_refresh_interval()
        self.state: dict[str, Any] = {
            "authenticated": False,
            "status": "waiting_for_addon",
            "points": None,
            "balance": None,
            "expiry_amount": None,
            "expiry_date": None,
            "expiry_message": None,
            "last_error": None,
            "last_update": None,
            "cookie_available": False,
            "cookie_names": [],
            "addon_version": "1.1.0",
        }

    async def start(self) -> None:
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        with suppress(OSError):
            SHARED_DIR.chmod(0o700)
        await asyncio.to_thread(atomic_write_json, STATE_FILE, self.state)

    async def load_cookies(self) -> tuple[list[dict[str, Any]], str]:
        try:
            storage = await asyncio.to_thread(
                lambda: json.loads(STORAGE_STATE_FILE.read_text(encoding="utf-8"))
            )
        except FileNotFoundError:
            return [], ""
        except (OSError, json.JSONDecodeError) as err:
            raise RuntimeError(f"Não foi possível ler os cookies do add-on: {err}") from err

        cookies = [
            cookie
            for cookie in storage.get("cookies", [])
            if str(cookie.get("domain", "")).lstrip(".").endswith("pingodoce.pt")
        ]
        header = "; ".join(
            f"{cookie['name']}={cookie['value']}"
            for cookie in cookies
            if cookie.get("name") and cookie.get("value") is not None
        )
        return cookies, header

    async def export_cookies(self) -> tuple[list[dict[str, Any]], str]:
        cookies, header = await self.load_cookies()
        await asyncio.to_thread(atomic_write_json, COOKIES_JSON_FILE, cookies)
        await asyncio.to_thread(atomic_write, COOKIE_HEADER_FILE, header)
        self.state["cookie_available"] = bool(header)
        self.state["cookie_names"] = sorted(
            {str(cookie.get("name")) for cookie in cookies if cookie.get("name")}
        )
        return cookies, header

    async def refresh(self) -> None:
        try:
            cookies, header = await self.export_cookies()
            if not header:
                self.state.update(
                    authenticated=False,
                    status="login_required",
                    last_error="Abra a interface Web do add-on e faça login no Pingo Doce.",
                    last_update=utcnow_iso(),
                )
                await asyncio.to_thread(atomic_write_json, STATE_FILE, self.state)
                return

            cookie_jar = aiohttp.CookieJar(unsafe=True)
            for cookie in cookies:
                cookie_jar.update_cookies({str(cookie["name"]): str(cookie["value"])})

            timeout = aiohttp.ClientTimeout(total=30)
            headers = {
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": BASE_URL + "/",
                "User-Agent": "Mozilla/5.0 PingoDoce-HomeAssistant/1.1",
            }
            async with aiohttp.ClientSession(
                cookie_jar=cookie_jar, timeout=timeout, headers=headers
            ) as session:
                async with session.get(BALANCE_URL) as response:
                    text = await response.text()
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        payload = None

            if response.status >= 300 or not isinstance(payload, dict) or not payload.get("success"):
                self.state.update(
                    authenticated=False,
                    status="login_required",
                    points=None,
                    balance=None,
                    expiry_amount=None,
                    expiry_date=None,
                    expiry_message=None,
                    last_error="A cookie existe, mas a sessão já não está autenticada.",
                    last_update=utcnow_iso(),
                )
            else:
                raw = payload.get("bpData") or {}
                points_value = parse_pt_number(raw.get("pointsBalance"))
                self.state.update(
                    authenticated=True,
                    status="authenticated",
                    points=int(points_value) if points_value is not None else None,
                    balance=parse_pt_number(raw.get("virtualMoneyBalance")),
                    expiry_amount=parse_pt_number(raw.get("virtualMoneyExpiry")),
                    expiry_date=raw.get("formattedDate"),
                    expiry_message=raw.get("expirationMessage"),
                    last_error=None,
                    last_update=utcnow_iso(),
                )
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, OSError) as err:
            self.state.update(
                authenticated=False,
                status="error",
                last_error=str(err),
                last_update=utcnow_iso(),
            )
            self.logger.warning("Falha ao atualizar a ponte: %s", err)

        await asyncio.to_thread(atomic_write_json, STATE_FILE, self.state)

    async def process_command(self, command_data: dict[str, Any]) -> None:
        command_id = str(command_data.get("id") or uuid.uuid4().hex)
        command = str(command_data.get("command", "")).strip().lower()
        result: dict[str, Any] = {
            "id": command_id,
            "command": command,
            "success": False,
            "completed_at": utcnow_iso(),
        }
        try:
            if command == "refresh":
                await self.refresh()
            elif command == "export_cookies":
                await self.export_cookies()
                await asyncio.to_thread(atomic_write_json, STATE_FILE, self.state)
            else:
                raise ValueError(f"Comando não suportado: {command}")
            result["success"] = True
        except Exception as err:  # noqa: BLE001
            result["error"] = str(err)
        result["completed_at"] = utcnow_iso()
        await asyncio.to_thread(atomic_write_json, COMMAND_RESULT_FILE, result)

    async def command_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(2)
            if not COMMAND_FILE.exists():
                continue
            try:
                command_data = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
                with suppress(OSError):
                    COMMAND_FILE.unlink()
                await self.process_command(command_data)
            except (OSError, json.JSONDecodeError) as err:
                self.logger.warning("Comando inválido: %s", err)
                with suppress(OSError):
                    COMMAND_FILE.unlink()

    async def refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            await self.refresh()
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), timeout=self.refresh_interval
                )
            except TimeoutError:
                pass


async def async_main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    bridge = AddonBridge()
    await bridge.start()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, bridge.stop_event.set)

    tasks = [
        asyncio.create_task(bridge.refresh_loop(), name="bridge_refresh"),
        asyncio.create_task(bridge.command_loop(), name="bridge_commands"),
    ]
    await bridge.stop_event.wait()
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    asyncio.run(async_main())
