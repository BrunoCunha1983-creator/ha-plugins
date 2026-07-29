from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BASE_URL = "https://www.pingodoce.pt"
ACCOUNT_URL = f"{BASE_URL}/home/area-pessoal?menu=orders"
DATA_URL = (
    f"{BASE_URL}/on/demandware.store/"
    "Sites-pingo-doce-Site/default/BPData-Info"
)
PROFILE_DIR = Path("/data/chromium-profile")
SESSION_DIR = Path("/data/session")
STORAGE_FILE = SESSION_DIR / "storage_state.json"
SHARED_DIR = Path("/config/pingo_doce_plus")
STATE_FILE = SHARED_DIR / "state.json"
COOKIE_FILE = SHARED_DIR / "cookie_header.txt"
COOKIES_FILE = SHARED_DIR / "cookies.json"
COMMAND_FILE = SHARED_DIR / "command.json"
RESULT_FILE = SHARED_DIR / "command_result.json"
OPTIONS_FILE = Path("/data/options.json")


def now() -> str:
    return datetime.now(UTC).isoformat()


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(value, encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    cleaned = "".join(c for c in str(value) if c.isdigit() or c in ",.-")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def options() -> tuple[int, int, str]:
    try:
        data = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return (
        max(60, int(data.get("refresh_interval", 300))),
        max(10, int(data.get("watchdog_interval", 30))),
        str(data.get("log_level", "info")).upper(),
    )


class PingoDocePlus:
    def __init__(self, refresh_interval: int, watchdog_interval: int) -> None:
        self.refresh_interval = refresh_interval
        self.watchdog_interval = watchdog_interval
        self.stop = asyncio.Event()
        self.lock = asyncio.Lock()
        self.playwright = None
        self.context = None
        self.page = None
        self.worker = None
        self.state: dict[str, Any] = {
            "authenticated": False,
            "status": "starting",
            "points": None,
            "balance": None,
            "expiry_amount": None,
            "expiry_date": None,
            "expiry_message": None,
            "cookie_available": False,
            "cookie_names": [],
            "last_update": None,
            "last_error": None,
            "addon_version": "2.0.0",
        }

    async def write_state(self) -> None:
        await asyncio.to_thread(write_json, STATE_FILE, self.state)

    async def export_session(self) -> None:
        if not self.context:
            return
        await self.context.storage_state(path=str(STORAGE_FILE))
        cookies = [
            c for c in await self.context.cookies([BASE_URL])
            if str(c.get("domain", "")).lstrip(".").endswith("pingodoce.pt")
        ]
        header = "; ".join(
            f"{c['name']}={c['value']}" for c in cookies if c.get("name")
        )
        await asyncio.to_thread(write_json, COOKIES_FILE, cookies)
        await asyncio.to_thread(write_text, COOKIE_FILE, header)
        self.state["cookie_available"] = bool(header)
        self.state["cookie_names"] = sorted({c["name"] for c in cookies if c.get("name")})

    async def ensure_pages(self, force: bool = False) -> None:
        if not self.context:
            raise RuntimeError("Chromium não iniciado")
        if not self.page or self.page.is_closed():
            self.page = await self.context.new_page()
        if force or not self.page.url.startswith(BASE_URL):
            with suppress(PlaywrightTimeoutError):
                await self.page.goto(ACCOUNT_URL, wait_until="domcontentloaded")
        await self.page.bring_to_front()
        if not self.worker or self.worker.is_closed():
            self.worker = await self.context.new_page()
        if not self.worker.url.startswith(BASE_URL):
            with suppress(PlaywrightTimeoutError):
                await self.worker.goto(BASE_URL, wait_until="domcontentloaded")

    async def start_browser(self) -> None:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("SingletonCookie", "SingletonLock", "SingletonSocket"):
            with suppress(OSError):
                (PROFILE_DIR / name).unlink()
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport=None,
            locale="pt-PT",
            timezone_id="Europe/Lisbon",
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--restore-last-session",
                "--start-maximized",
                "--password-store=basic",
                "--use-mock-keychain",
            ],
        )
        self.context.set_default_timeout(30_000)
        if STORAGE_FILE.exists():
            try:
                saved = json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
                if saved.get("cookies"):
                    await self.context.add_cookies(saved["cookies"])
            except Exception:
                logging.exception("Não foi possível restaurar a sessão guardada")
        pages = [p for p in self.context.pages if not p.is_closed()]
        self.page = pages[0] if pages else await self.context.new_page()
        self.worker = await self.context.new_page()
        await self.ensure_pages(force=True)

    async def close_browser(self) -> None:
        if self.context:
            with suppress(Exception):
                await self.export_session()
                await self.context.close()
        if self.playwright:
            with suppress(Exception):
                await self.playwright.stop()
        self.context = self.page = self.worker = self.playwright = None

    async def restart_browser(self) -> None:
        await self.close_browser()
        await asyncio.sleep(1)
        await self.start_browser()
        await self.refresh()

    async def refresh(self) -> None:
        async with self.lock:
            try:
                await self.ensure_pages()
                result = await self.worker.evaluate(
                    """async url => {
                      try {
                        const r = await fetch(url, {credentials:'include', cache:'no-store',
                          headers:{'Accept':'application/json, text/plain, */*',
                                   'X-Requested-With':'XMLHttpRequest'}});
                        const text = await r.text();
                        let data = null; try { data = JSON.parse(text); } catch (_) {}
                        return {ok:r.ok, status:r.status, data};
                      } catch (e) { return {ok:false, error:String(e)}; }
                    }""",
                    DATA_URL,
                )
                payload = result.get("data") if isinstance(result, dict) else None
                if not result.get("ok") or not isinstance(payload, dict) or not payload.get("success"):
                    self.state.update(
                        authenticated=False,
                        status="login_required",
                        points=None,
                        balance=None,
                        expiry_amount=None,
                        expiry_date=None,
                        expiry_message=None,
                        last_error="Abra a interface Web do add-on e faça login no Pingo Doce.",
                        last_update=now(),
                    )
                else:
                    data = payload.get("bpData") or {}
                    points = number(data.get("pointsBalance"))
                    self.state.update(
                        authenticated=True,
                        status="authenticated",
                        points=int(points) if points is not None else None,
                        balance=number(data.get("virtualMoneyBalance")),
                        expiry_amount=number(data.get("virtualMoneyExpiry")),
                        expiry_date=data.get("formattedDate"),
                        expiry_message=data.get("expirationMessage"),
                        last_error=None,
                        last_update=now(),
                    )
                await self.export_session()
            except Exception as err:
                self.state.update(
                    authenticated=False,
                    status="error",
                    last_error=str(err),
                    last_update=now(),
                )
                logging.exception("Erro ao atualizar Pingo Doce Plus")
            await self.write_state()

    async def command_loop(self) -> None:
        while not self.stop.is_set():
            await asyncio.sleep(1)
            if not COMMAND_FILE.exists():
                continue
            try:
                command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
                COMMAND_FILE.unlink(missing_ok=True)
                name = str(command.get("command", ""))
                if name == "refresh":
                    await self.refresh()
                elif name == "open_login":
                    async with self.lock:
                        await self.ensure_pages(force=True)
                elif name == "restart_browser":
                    await self.restart_browser()
                elif name == "export_cookies":
                    await self.export_session()
                    await self.write_state()
                else:
                    raise ValueError(f"Comando desconhecido: {name}")
                result = {"id": command.get("id"), "success": True, "completed_at": now()}
            except Exception as err:
                result = {"id": command.get("id") if 'command' in locals() else None,
                          "success": False, "error": str(err), "completed_at": now()}
            await asyncio.to_thread(write_json, RESULT_FILE, result)

    async def run(self) -> None:
        await self.write_state()
        await self.start_browser()
        await self.refresh()
        tasks = [asyncio.create_task(self.command_loop())]
        try:
            while not self.stop.is_set():
                await asyncio.sleep(min(self.refresh_interval, self.watchdog_interval))
                if not self.context or not self.page or self.page.is_closed():
                    await self.restart_browser()
                else:
                    await self.refresh()
        finally:
            for task in tasks:
                task.cancel()
            await self.close_browser()


async def main() -> None:
    refresh, watchdog, level = options()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))
    app = PingoDocePlus(refresh, watchdog)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, app.stop.set)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
