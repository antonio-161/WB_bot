"""
Модуль для получения x-pow токена через Playwright.
WB использует этот токен для защиты от ботов.
"""
import asyncio
import logging
from typing import Optional
from playwright.async_api import async_playwright
import time

logger = logging.getLogger(__name__)


class XPowFetcher:
    """Класс для получения x-pow токена с помощью Playwright."""

    def __init__(self):
        self._browser = None
        self._context = None
        self._page = None
        self._last_token = None
        self._last_token_time = 0
        self._token_ttl = 300  # Токен живёт 5 минут
        self._lock = asyncio.Lock()
    
    async def init(self):
        """Инициализация браузера."""
        if self._browser is None:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
            logger.info("Playwright браузер инициализирован для x-pow")
    
    async def close(self):
        """Закрытие браузера."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
            logger.info("Playwright браузер закрыт")
    
    async def get_xpow_token(self, nm_id: int, dest: int) -> Optional[str]:
        """
        Получить x-pow токен для запроса к WB API.
        
        Метод:
        1. Открывает страницу товара в браузере
        2. Перехватывает запрос к cards API
        3. Извлекает x-pow из заголовков
        """
        async with self._lock:
            # Проверяем кэш
            current_time = time.time()
            if self._last_token and (current_time - self._last_token_time) < self._token_ttl:
                logger.debug(f"Используем закэшированный x-pow токен")
                return self._last_token
            
            try:
                await self.init()
                
                # Создаём новую страницу
                page = await self._context.new_page()
                
                # Переменная для хранения токена
                captured_token = None
                token_captured = asyncio.Event()
                
                # Обработчик для перехвата запросов
                async def handle_request(route, request):
                    # Ищем запрос к cards API
                    if "u-card.wb.ru/cards/v4/detail" in request.url or "card.wb.ru" in request.url:
                        headers = request.headers
                        if "x-pow" in headers:
                            nonlocal captured_token
                            captured_token = headers["x-pow"]
                            logger.info(f"Перехвачен x-pow токен: {captured_token[:25]}...")
                            token_captured.set()
                    
                    # Продолжаем запрос
                    await route.continue_()
                
                # Включаем перехват запросов
                await page.route("**/*", handle_request)
                
                # Открываем страницу товара
                url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
                logger.debug(f"Открываю страницу товара {nm_id} для получения x-pow")
                
                # Используем domcontentloaded вместо networkidle (быстрее и надёжнее)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                except Exception as e:
                    logger.warning(f"Ошибка при загрузке страницы (игнорируем): {e}")
                
                # Ждём токен максимум 10 секунд
                try:
                    await asyncio.wait_for(token_captured.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Токен не перехвачен за 10 секунд для товара {nm_id}")
                
                # Закрываем страницу
                await page.close()
                
                if captured_token:
                    self._last_token = captured_token
                    self._last_token_time = current_time
                    logger.info(f"X-pow токен успешно получен")
                    return captured_token
                else:
                    logger.warning(f"Не удалось перехватить x-pow токен для товара {nm_id}")
                    return None
                    
            except Exception as e:
                logger.exception(f"Ошибка при получении x-pow токена: {e}")
                return None
    
    async def get_xpow_simple(self, nm_id: int, dest: int) -> Optional[str]:
        """
        Упрощённый метод получения x-pow.
        Открывает главную страницу WB и пытается перехватить любой запрос с токеном.
        Быстрее, но менее специфичен.
        """
        async with self._lock:
            # Проверяем кэш
            current_time = time.time()
            if self._last_token and (current_time - self._last_token_time) < self._token_ttl:
                logger.debug(f"Используем закэшированный x-pow токен")
                return self._last_token
            
            try:
                await self.init()
                
                # Создаём новую страницу
                page = await self._context.new_page()
                
                captured_token = None
                token_captured = asyncio.Event()
                
                # Обработчик для перехвата ЛЮБЫХ запросов с x-pow
                async def handle_request(route, request):
                    nonlocal captured_token
                    headers = request.headers
                    if "x-pow" in headers and not captured_token:
                        captured_token = headers["x-pow"]
                        logger.info(f"Перехвачен x-pow токен (simple): {captured_token[:25]}...")
                        token_captured.set()
                    
                    await route.continue_()
                
                await page.route("**/*", handle_request)
                
                # Открываем главную страницу (быстрее загружается)
                logger.debug(f"Открываю главную страницу WB для получения x-pow")
                
                try:
                    await page.goto("https://www.wildberries.ru", wait_until="domcontentloaded", timeout=10000)
                except Exception as e:
                    logger.warning(f"Ошибка загрузки главной (игнорируем): {e}")
                
                # Ждём токен 5 секунд
                try:
                    await asyncio.wait_for(token_captured.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Токен не перехвачен за 5 секунд (simple метод)")
                
                await page.close()
                
                if captured_token:
                    self._last_token = captured_token
                    self._last_token_time = current_time
                    logger.info(f"X-pow токен успешно получен (simple метод)")
                    return captured_token
                else:
                    return None
                    
            except Exception as e:
                logger.exception(f"Ошибка в get_xpow_simple: {e}")
                return None


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
