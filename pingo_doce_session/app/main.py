from __future__ import annotations

import asyncio
import json
import logging
import re
import signal
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp
from playwright.async_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

BASE_URL = "https://www.pingodoce.pt"
ACCOUNT_URL = "https://www.pingodoce.pt/home/area-pessoal?menu=orders"
BALANCE_URL = (
    "https://www.pingodoce.pt/on/demandware.store/"
    "Sites-pingo-doce-Site/default/BPData-Info"
)
OPTIONS_FILE = Path("/data/options.json")
PROFILE_DIR = Path("/data/chromium-profile")
SESSION_DIR = Path("/data/session")
STORAGE_STATE_FILE = SESSION_DIR / "storage_state.json"
HA_API = "http://supervisor/core/api"


@dataclass(slots=True)
class Options:
    refresh_interval: int = 300
    watchdog_interval: int = 30
    log_level: str = "info"


def load_options() -> Options:
    try:
        raw = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}

    refresh = max(60, int(raw.get("refresh_interval", 300)))
    watchdog = max(10, int(raw.get("watchdog_interval", 30)))
    level = str(raw.get("log_level", "info")).lower()
    if level not in {"debug", "info", "warning", "error"}:
        level = "info"
    return Options(refresh_interval=refresh, watchdog_interval=watchdog, log_level=level)


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def parse_pt_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    cleaned = re.sub(r"[^0-9,.-]", "", text)
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


class HomeAssistantPublisher:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._token = str(__import__("os").environ.get("SUPERVISOR_TOKEN", ""))
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def set_state(self, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        if not self._session or not self._token:
            return
        try:
            async with self._session.post(
                f"{HA_API}/states/{entity_id}",
                json={"state": state, "attributes": attributes},
            ) as response:
                if response.status >= 300:
                    body = await response.text()
                    self._logger.warning(
                        "Falha ao publicar %s no Home Assistant: HTTP %s %s",
                        entity_id,
                        response.status,
                        body[:200],
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            self._logger.warning("Falha ao comunicar com o Home Assistant: %s", err)

    async def publish(
        self,
        *,
        authenticated: bool,
        status: str,
        points: int | None,
        balance: float | None,
        expiry_amount: float | None,
        expiry_date: str | None,
        expiry_message: str | None,
        last_error: str | None,
    ) -> None:
        common = {
            "integration": "Pingo Doce Add-on",
            "last_update": utcnow_iso(),
        }
        await self.set_state(
            "binary_sensor.pingo_doce_sessao",
            "on" if authenticated else "off",
            {
                **common,
                "friendly_name": "Pingo Doce — Sessão",
                "device_class": "connectivity",
                "status": status,
                "last_error": last_error,
                "icon": "mdi:account-key",
            },
        )
        await self.set_state(
            "sensor.pingo_doce_pontos",
            str(points) if points is not None else "unknown",
            {
                **common,
                "friendly_name": "Pingo Doce — Pontos",
                "unit_of_measurement": "pontos",
                "icon": "mdi:star-circle",
            },
        )
        await self.set_state(
            "sensor.pingo_doce_saldo",
            str(balance) if balance is not None else "unknown",
            {
                **common,
                "friendly_name": "Pingo Doce — Saldo",
                "unit_of_measurement": "EUR",
                "device_class": "monetary",
                "icon": "mdi:cash-multiple",
            },
        )
        await self.set_state(
            "sensor.pingo_doce_saldo_validade",
            expiry_date or "unknown",
            {
                **common,
                "friendly_name": "Pingo Doce — Validade do saldo",
                "amount_expiring": expiry_amount,
                "amount_expiring_unit": "EUR",
                "message": expiry_message,
                "icon": "mdi:calendar-clock",
            },
        )


class PingoDoceKeeper:
    def __init__(self, options: Options, publisher: HomeAssistantPublisher, logger: logging.Logger) -> None:
        self.options = options
        self.publisher = publisher
        self.logger = logger
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.worker: Page | None = None
        self.lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.authenticated = False
        self.status = "starting"
        self.last_error: str | None = None

    async def start(self) -> None:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        await self.start_browser()

    async def stop(self) -> None:
        self.stop_event.set()
        await self.save_storage_state()
        await self.close_browser()

    async def restore_storage_state(self) -> None:
        if not self.context or not STORAGE_STATE_FILE.exists():
            return
        try:
            state = json.loads(STORAGE_STATE_FILE.read_text(encoding="utf-8"))
            cookies = state.get("cookies") or []
            if cookies:
                await self.context.add_cookies(cookies)
                self.logger.info("Cookies da sessão anterior restaurados")
        except (OSError, json.JSONDecodeError, PlaywrightError, TypeError) as err:
            self.logger.warning("Não foi possível restaurar a sessão guardada: %s", err)

    async def save_storage_state(self) -> None:
        if not self.context:
            return
        try:
            await self.context.storage_state(path=str(STORAGE_STATE_FILE))
        except PlaywrightError as err:
            self.logger.debug("Não foi possível guardar o estado do navegador: %s", err)

    async def start_browser(self) -> None:
        async with self.lock:
            self.status = "starting"
            self.last_error = None
            if not self.playwright:
                self.playwright = await async_playwright().start()

            for name in ("SingletonCookie", "SingletonLock", "SingletonSocket"):
                with suppress(OSError):
                    (PROFILE_DIR / name).unlink()

            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=False,
                viewport=None,
                locale="pt-PT",
                timezone_id="Europe/Lisbon",
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-session-crashed-bubble",
                    "--restore-last-session",
                    "--start-maximized",
                    "--password-store=basic",
                    "--use-mock-keychain",
                ],
            )
            self.context.set_default_timeout(30_000)
            self.context.set_default_navigation_timeout(60_000)
            await self.restore_storage_state()

            pages = [page for page in self.context.pages if not page.is_closed()]
            self.page = pages[0] if pages else await self.context.new_page()
            self.worker = await self.context.new_page()
            await self.ensure_pages_locked(force=True)
            self.status = "running"

        await self.refresh()

    async def close_browser(self) -> None:
        context, self.context = self.context, None
        self.page = None
        self.worker = None
        if context:
            with suppress(Exception):
                await context.close()
        playwright, self.playwright = self.playwright, None
        if playwright:
            with suppress(Exception):
                await playwright.stop()

    async def restart_browser(self) -> None:
        self.logger.warning("A reiniciar o Chromium")
        await self.save_storage_state()
        await self.close_browser()
        await asyncio.sleep(1)
        await self.start_browser()

    async def ensure_pages_locked(self, force: bool = False) -> None:
        if not self.context:
            raise RuntimeError("Chromium indisponível")
        if not self.page or self.page.is_closed():
            self.page = await self.context.new_page()
        if force or not (self.page.url or "").startswith(BASE_URL):
            try:
                await self.page.goto(ACCOUNT_URL, wait_until="domcontentloaded", timeout=60_000)
            except PlaywrightTimeoutError:
                self.logger.warning("Timeout ao abrir a área pessoal; a página ficou aberta")
        await self.page.bring_to_front()

        if not self.worker or self.worker.is_closed():
            self.worker = await self.context.new_page()
        if not (self.worker.url or "").startswith(BASE_URL):
            try:
                await self.worker.goto(BASE_URL, wait_until="domcontentloaded", timeout=60_000)
            except PlaywrightTimeoutError:
                self.logger.warning("Timeout ao preparar o separador interno")

    async def refresh(self) -> None:
        async with self.lock:
            try:
                if not self.context:
                    raise RuntimeError("Chromium não iniciado")
                await self.ensure_pages_locked()
                assert self.worker is not None

                result = await self.worker.evaluate(
                    """
                    async ({url}) => {
                      try {
                        const response = await fetch(url, {
                          method: 'GET',
                          credentials: 'include',
                          cache: 'no-store',
                          headers: {
                            'Accept': 'application/json, text/plain, */*',
                            'X-Requested-With': 'XMLHttpRequest'
                          }
                        });
                        const text = await response.text();
                        let json = null;
                        try { json = JSON.parse(text); } catch (_) {}
                        return {ok: response.ok, status: response.status, json};
                      } catch (error) {
                        return {ok: false, status: 0, error: String(error)};
                      }
                    }
                    """,
                    {"url": BALANCE_URL},
                )

                payload = result.get("json") if isinstance(result, dict) else None
                if not result.get("ok") or not isinstance(payload, dict) or not payload.get("success"):
                    self.authenticated = False
                    self.status = "login_required"
                    self.last_error = "Sessão não autenticada. Abra a interface Web do add-on e faça login."
                    await self.publisher.publish(
                        authenticated=False,
                        status=self.status,
                        points=None,
                        balance=None,
                        expiry_amount=None,
                        expiry_date=None,
                        expiry_message=None,
                        last_error=self.last_error,
                    )
                    return

                raw = payload.get("bpData") or {}
                points_value = parse_pt_number(raw.get("pointsBalance"))
                points = int(points_value) if points_value is not None else None
                balance = parse_pt_number(raw.get("virtualMoneyBalance"))
                expiry_amount = parse_pt_number(raw.get("virtualMoneyExpiry"))
                expiry_date = raw.get("formattedDate")
                expiry_message = raw.get("expirationMessage")

                self.authenticated = True
                self.status = "authenticated"
                self.last_error = None
                await self.save_storage_state()
                await self.publisher.publish(
                    authenticated=True,
                    status=self.status,
                    points=points,
                    balance=balance,
                    expiry_amount=expiry_amount,
                    expiry_date=str(expiry_date) if expiry_date is not None else None,
                    expiry_message=str(expiry_message) if expiry_message is not None else None,
                    last_error=None,
                )
                self.logger.info("Sessão Pingo Doce ativa; dados atualizados")

            except (PlaywrightError, RuntimeError, OSError) as err:
                self.authenticated = False
                self.status = "error"
                self.last_error = str(err)
                self.logger.warning("Falha na atualização: %s", err)
                await self.publisher.publish(
                    authenticated=False,
                    status=self.status,
                    points=None,
                    balance=None,
                    expiry_amount=None,
                    expiry_date=None,
                    expiry_message=None,
                    last_error=self.last_error,
                )

    async def watchdog_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(self.options.watchdog_interval)
            if self.stop_event.is_set():
                return
            try:
                if not self.context:
                    await self.restart_browser()
                    continue
                if not self.page or self.page.is_closed():
                    async with self.lock:
                        await self.ensure_pages_locked(force=True)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                self.logger.exception("Erro no watchdog: %s", err)
                with suppress(Exception):
                    await self.restart_browser()

    async def refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(self.options.refresh_interval)
            if self.stop_event.is_set():
                return
            await self.refresh()


async def async_main() -> None:
    options = load_options()
    logging.basicConfig(
        level=getattr(logging, options.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("pingo_doce_addon")
    publisher = HomeAssistantPublisher(logger)
    keeper = PingoDoceKeeper(options, publisher, logger)
    await publisher.start()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, keeper.stop_event.set)

    try:
        await keeper.start()
        tasks = [
            asyncio.create_task(keeper.watchdog_loop(), name="watchdog"),
            asyncio.create_task(keeper.refresh_loop(), name="refresh"),
        ]
        await keeper.stop_event.wait()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
    finally:
        await keeper.stop()
        await publisher.close()


if __name__ == "__main__":
    asyncio.run(async_main())
