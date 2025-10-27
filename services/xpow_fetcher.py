"""
Модуль для получения x-pow токена через Playwright.
WB использует этот токен для защиты от ботов.
"""
import asyncio
import logging
import time
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from utils.decorators import retry_on_error

logger = logging.getLogger(__name__)


class XPowFetcher:
    """Класс для получения x-pow токена с помощью Playwright."""

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._last_token: Optional[str] = None
        self._last_token_time: float = 0
        self._token_ttl: int = 300  # токен живёт 5 минут
        self._lock = asyncio.Lock()

    async def init(self):
        """Инициализация браузера."""
        if self._browser is not None:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        )
        logger.info("Playwright браузер инициализирован для x-pow")

    async def close(self):
        """Закрытие браузера и Playwright."""
        try:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._context = None
            logger.info("Playwright браузер закрыт")
        except Exception as e:
            logger.warning(f"Ошибка при закрытии XPowFetcher: {e}")

    @retry_on_error(max_attempts=3, delay=2)
    async def get_xpow_token(self, nm_id: int, dest: int) -> Optional[str]:
        """Получить x-pow токен для запроса к WB API."""
        async with self._lock:
            current_time = time.time()
            if self._last_token and (current_time - self._last_token_time) < self._token_ttl:
                logger.debug("Используем закэшированный x-pow токен")
                return self._last_token

            await self.init()
            page: Optional[Page] = None
            try:
                page = await self._context.new_page()
                captured_token: Optional[str] = None
                token_event = asyncio.Event()

                async def handle_request(route, request):
                    nonlocal captured_token
                    if "u-card.wb.ru/cards/v4/detail" in request.url or "card.wb.ru" in request.url:
                        headers = request.headers
                        if "x-pow" in headers:
                            captured_token = headers["x-pow"]
                            logger.info(f"Перехвачен x-pow токен: {captured_token[:25]}...")
                            token_event.set()
                    await route.continue_()

                await page.route("**/*", handle_request)

                url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
                logger.debug(f"Открываю страницу товара {nm_id} для получения x-pow")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                except Exception as e:
                    logger.warning(f"Ошибка при загрузке страницы (игнорируем): {e}")

                try:
                    await asyncio.wait_for(token_event.wait(), timeout=20.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Токен не перехвачен за 20 секунд для товара {nm_id}")

                if captured_token:
                    self._last_token = captured_token
                    self._last_token_time = time.time()
                    logger.info("X-pow токен успешно получен")
                    return captured_token
                else:
                    logger.warning(f"Не удалось перехватить x-pow токен для товара {nm_id}")
                    return None
            finally:
                if page:
                    await page.close()

    @retry_on_error(max_attempts=3, delay=2)
    async def get_xpow_simple(self) -> Optional[str]:
        """Упрощённый метод получения x-pow через главную страницу WB."""
        async with self._lock:
            current_time = time.time()
            if self._last_token and (current_time - self._last_token_time) < self._token_ttl:
                return self._last_token

            await self.init()
            page: Optional[Page] = None
            try:
                page = await self._context.new_page()
                captured_token: Optional[str] = None
                token_event = asyncio.Event()

                async def handle_request(route, request):
                    nonlocal captured_token
                    headers = request.headers
                    if "x-pow" in headers and not captured_token:
                        captured_token = headers["x-pow"]
                        logger.info(f"Перехвачен x-pow токен (simple): {captured_token[:25]}...")
                        token_event.set()
                    await route.continue_()

                await page.route("**/*", handle_request)

                logger.debug("Открываю главную страницу WB для получения x-pow")
                try:
                    await page.goto("https://www.wildberries.ru", wait_until="domcontentloaded", timeout=10000)
                except Exception as e:
                    logger.warning(f"Ошибка загрузки главной (игнорируем): {e}")

                try:
                    await asyncio.wait_for(token_event.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Токен не перехвачен за 5 секунд (simple метод)")

                if captured_token:
                    self._last_token = captured_token
                    self._last_token_time = time.time()
                    return captured_token
                return None
            finally:
                if page:
                    await page.close()


# Глобальный экземпляр
_xpow_fetcher: Optional[XPowFetcher] = None


async def get_xpow_fetcher() -> XPowFetcher:
    """Получить глобальный экземпляр XPowFetcher."""
    global _xpow_fetcher
    if _xpow_fetcher is None:
        _xpow_fetcher = XPowFetcher()
        await _xpow_fetcher.init()
    return _xpow_fetcher


async def close_xpow_fetcher():
    """Закрыть глобальный экземпляр."""
    global _xpow_fetcher
    if _xpow_fetcher:
        await _xpow_fetcher.close()
        _xpow_fetcher = None
