from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import (
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from .parsers import parse_coupons_html, parse_orders_html
from .utils import (
    ACCOUNT_URL,
    BALANCE_URL,
    BASE_URL,
    COMMAND_FILE,
    COMMAND_RESULT_FILE,
    COUPONS_URL,
    PROFILE_DIR,
    SESSION_DIR,
    SHARED_DIR,
    STATE_FILE,
    STATE_MEMORY_FILE,
    STORAGE_STATE_FILE,
    Options,
    atomic_write_json,
    load_previous_state,
    parse_pt_number,
    utcnow_iso,
)


class PingoDocePlusKeeper:
    def __init__(self, options: Options, logger: logging.Logger) -> None:
        self.options = options
        self.logger = logger
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.worker: Page | None = None
        self.lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.previous_state = load_previous_state()
        self.state: dict[str, Any] = self._base_state()

    @staticmethod
    def _base_state() -> dict[str, Any]:
        return {
            "version": "2.0.0",
            "authenticated": False,
            "status": "starting",
            "last_error": None,
            "last_update": None,
            "session_expiry": None,
            "browser_running": False,
            "browser_url": None,
            "points": None,
            "balance": None,
            "expiry_amount": None,
            "expiry_date": None,
            "expiry_message": None,
            "active_orders": 0,
            "current_order": None,
            "history": [],
            "purchase_history_count": 0,
            "last_order": None,
            "detected_words": [],
            "website_changed": False,
            "coupon_count": None,
            "active_coupon_count": None,
            "coupons": [],
            "capabilities": {
                "session": True,
                "balance": True,
                "orders": True,
                "history": True,
                "coupons": "best_effort",
            },
        }

    async def start(self) -> None:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        with suppress(OSError):
            SHARED_DIR.chmod(0o700)
        await self.start_browser()

    async def stop(self) -> None:
        self.stop_event.set()
        await self.save_storage_state()
        await self.close_browser()

    async def write_state(self) -> None:
        await asyncio.to_thread(atomic_write_json, STATE_FILE, self.state, 0o600)
        await asyncio.to_thread(atomic_write_json, STATE_MEMORY_FILE, self.state, 0o600)
        self.previous_state = dict(self.state)

    async def restore_storage_state(self) -> None:
        if not self.context or not STORAGE_STATE_FILE.exists():
            return
        try:
            storage = json.loads(STORAGE_STATE_FILE.read_text(encoding="utf-8"))
            cookies = storage.get("cookies") or []
            if cookies:
                await self.context.add_cookies(cookies)
                self.logger.info("Sessão anterior restaurada")
        except (OSError, json.JSONDecodeError, PlaywrightError, TypeError) as err:
            self.logger.warning("Não foi possível restaurar a sessão: %s", err)

    async def save_storage_state(self) -> None:
        if not self.context:
            return
        try:
            await self.context.storage_state(path=str(STORAGE_STATE_FILE))
            with suppress(OSError):
                STORAGE_STATE_FILE.chmod(0o600)
        except PlaywrightError as err:
            self.logger.debug("Não foi possível guardar a sessão: %s", err)

    async def start_browser(self) -> None:
        async with self.lock:
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
            self.state["browser_running"] = True
            self.state["browser_url"] = self.page.url
        await self.refresh()

    async def close_browser(self) -> None:
        context, self.context = self.context, None
        self.page = None
        self.worker = None
        self.state["browser_running"] = False
        if context:
            with suppress(Exception):
                await context.close()
        playwright, self.playwright = self.playwright, None
        if playwright:
            with suppress(Exception):
                await playwright.stop()

    async def restart_browser(self) -> None:
        self.logger.warning("A reiniciar o Chromium do Pingo Doce Plus")
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
                await self.page.goto(ACCOUNT_URL, wait_until="domcontentloaded")
            except PlaywrightTimeoutError:
                self.logger.warning("Timeout ao abrir a área pessoal; a página ficou aberta")
        if not self.worker or self.worker.is_closed():
            self.worker = await self.context.new_page()
        if not (self.worker.url or "").startswith(BASE_URL):
            try:
                await self.worker.goto(BASE_URL, wait_until="domcontentloaded")
            except PlaywrightTimeoutError:
                self.logger.warning("Timeout ao preparar o separador interno")
        self.state["browser_url"] = self.page.url

    async def browser_fetch(self, url: str) -> dict[str, Any]:
        assert self.worker is not None
        result = await self.worker.evaluate(
            """
            async ({url}) => {
              try {
                const response = await fetch(url, {
                  method: 'GET', credentials: 'include', cache: 'no-store',
                  headers: {
                    'Accept': 'application/json, text/html, text/plain, */*',
                    'X-Requested-With': 'XMLHttpRequest'
                  }
                });
                return {
                  ok: response.ok,
                  status: response.status,
                  url: response.url,
                  text: await response.text()
                };
              } catch (error) {
                return {ok: false, status: 0, url, text: '', error: String(error)};
              }
            }
            """,
            {"url": url},
        )
        return result if isinstance(result, dict) else {"ok": False, "status": 0, "text": ""}

    async def session_expiry(self) -> str | None:
        if not self.context:
            return None
        cookies = await self.context.cookies([BASE_URL])
        expirations = [float(c["expires"]) for c in cookies if float(c.get("expires", -1)) > 0]
        if not expirations:
            return None
        return datetime.fromtimestamp(min(expirations), UTC).isoformat()

    async def refresh(self) -> None:
        async with self.lock:
            try:
                await self.ensure_pages_locked()
                balance_result = await self.browser_fetch(BALANCE_URL)
                orders_result = await self.browser_fetch(ACCOUNT_URL)

                try:
                    balance_payload = json.loads(balance_result.get("text") or "")
                except json.JSONDecodeError:
                    balance_payload = None

                authenticated = bool(
                    balance_result.get("ok")
                    and isinstance(balance_payload, dict)
                    and balance_payload.get("success")
                )
                if not authenticated:
                    self.state.update(
                        authenticated=False,
                        status="login_required",
                        last_error="Abra a interface Web do add-on e faça login uma única vez.",
                        last_update=utcnow_iso(),
                        session_expiry=None,
                        browser_running=True,
                        browser_url=self.page.url if self.page else None,
                        points=None,
                        balance=None,
                        expiry_amount=None,
                        expiry_date=None,
                        expiry_message=None,
                        active_orders=0,
                        current_order=None,
                        history=[],
                        purchase_history_count=0,
                        last_order=None,
                        coupon_count=None,
                        active_coupon_count=None,
                        coupons=[],
                        detected_words=[],
                        website_changed=False,
                    )
                    await self.write_state()
                    return

                raw = balance_payload.get("bpData") or {}
                orders = parse_orders_html(orders_result.get("text") or "")
                coupons = {"coupons": [], "coupon_count": None, "active_coupon_count": None}
                with suppress(Exception):
                    coupon_result = await self.browser_fetch(COUPONS_URL)
                    if coupon_result.get("ok"):
                        coupons = parse_coupons_html(coupon_result.get("text") or "")

                previous_fingerprint = self.previous_state.get("site_fingerprint")
                current_fingerprint = orders.pop("fingerprint")
                changed = bool(previous_fingerprint and previous_fingerprint != current_fingerprint)
                points_value = parse_pt_number(raw.get("pointsBalance"))

                self.state.update(
                    authenticated=True,
                    status="authenticated",
                    last_error=None,
                    last_update=utcnow_iso(),
                    session_expiry=await self.session_expiry(),
                    browser_running=True,
                    browser_url=self.page.url if self.page else None,
                    points=int(points_value) if points_value is not None else None,
                    balance=parse_pt_number(raw.get("virtualMoneyBalance")),
                    expiry_amount=parse_pt_number(raw.get("virtualMoneyExpiry")),
                    expiry_date=raw.get("formattedDate"),
                    expiry_message=raw.get("expirationMessage"),
                    website_changed=changed,
                    site_fingerprint=current_fingerprint,
                    **orders,
                    **coupons,
                )
                await self.save_storage_state()
                await self.write_state()
                self.logger.info("Pingo Doce Plus atualizado com sessão autenticada")
            except (PlaywrightError, RuntimeError, OSError) as err:
                self.state.update(
                    authenticated=False,
                    status="error",
                    last_error=str(err),
                    last_update=utcnow_iso(),
                    browser_running=bool(self.context),
                )
                await self.write_state()
                self.logger.warning("Falha na atualização: %s", err)

    async def open_login(self) -> None:
        async with self.lock:
            await self.ensure_pages_locked(force=True)
            assert self.page is not None
            await self.page.bring_to_front()
            self.state["browser_url"] = self.page.url
            await self.write_state()

    async def process_command(self, data: dict[str, Any]) -> None:
        command_id = str(data.get("id") or uuid.uuid4().hex)
        command = str(data.get("command", "")).strip().lower()
        result: dict[str, Any] = {
            "id": command_id,
            "command": command,
            "success": False,
            "completed_at": utcnow_iso(),
        }
        try:
            if command == "refresh":
                await self.refresh()
            elif command == "open_login":
                await self.open_login()
            elif command == "restart_browser":
                await self.restart_browser()
            else:
                raise ValueError(f"Comando não suportado: {command}")
            result["success"] = True
        except Exception as err:  # noqa: BLE001
            result["error"] = str(err)
        result["completed_at"] = utcnow_iso()
        await asyncio.to_thread(atomic_write_json, COMMAND_RESULT_FILE, result, 0o600)

    async def command_loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(1)
            if not COMMAND_FILE.exists():
                continue
            try:
                data = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
                with suppress(OSError):
                    COMMAND_FILE.unlink()
                await self.process_command(data)
            except (OSError, json.JSONDecodeError) as err:
                self.logger.warning("Comando inválido: %s", err)
                with suppress(OSError):
                    COMMAND_FILE.unlink()

    async def refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=self.options.refresh_interval)
            except TimeoutError:
                await self.refresh()

    async def watchdog_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=self.options.watchdog_interval)
                return
            except TimeoutError:
                pass
            try:
                if not self.context or not self.page or self.page.is_closed():
                    await self.restart_browser()
            except Exception as err:  # noqa: BLE001
                self.logger.exception("Erro no watchdog: %s", err)
