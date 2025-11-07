"""
Оптимизированный модуль для получения x-pow токена.
Использует ОТДЕЛЬНУЮ прогревочную сессию в начале каждого цикла.
"""
import asyncio
import logging
import time
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Request
from constants import DEFAULT_DEST

logger = logging.getLogger(__name__)


def get_api_url(dest: int, nm_id: int) -> str:
    """Генерирует URL для API запроса к Wildberries."""
    return (
        f"https://www.wildberries.ru/__internal/u-card/cards/v4/detail"
        f"?appType=1&curr=rub&dest={dest}&spp=30&hide_dtype=11&ab_testing=false&lang=ru&nm={nm_id}"
    )


class XPowFetcher:
    """Оптимизированный класс для получения x-pow токенов."""

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()
        self._permanent_page: Optional[Page] = None
        
        # ✅ РАБОЧАЯ СЕССИЯ
        self._current_session: Optional[Dict] = None
        self._session_created_at: float = 0
        self._session_ttl: int = 120  # 2 минуты
        self._session_request_count: int = 0
        self._max_requests_per_session: int = 20  # По 50 товаров на сессию
        
        # ✅ ФЛАГ ПРОГРЕВА (сбрасывается при закрытии браузера)
        self._warmup_done: bool = False
        
        self._session_stats = {
            "total_sessions": 0,
            "total_requests": 0,
            "warmup_sessions": 0
        }

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
        self._permanent_page = await self._context.new_page()
        logger.info("🌐 Playwright браузер инициализирован (создана постоянная вкладка)")

    async def close(self):
        """Закрытие браузера и сброс состояния."""
        try:

            if self._permanent_page and not self._permanent_page.is_closed():
                await self._permanent_page.close()
                self._permanent_page = None
                logger.debug("🗑️ Постоянная вкладка закрыта")

            if self._browser:
                await self._browser.close()
                self._browser = None
            
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            
            self._context = None
            self._current_session = None
            self._warmup_done = False
            
            logger.info("🔴 Playwright браузер закрыт")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии XPowFetcher: {e}")

    async def _create_new_session(self, nm_id: int, dest: int) -> Optional[Dict]:
        """Создать новую сессию (заголовки + x-pow)."""
        self._session_stats["total_sessions"] += 1
        session_num = self._session_stats["total_sessions"]
        
        logger.info(f"🔄 Создаю сессию #{session_num} для nm={nm_id}")

        if not self._context:
            logger.error(f"❌ Браузер не инициализирован для сессии #{session_num}!")
            return None

        page = self._permanent_page

        try:
            captured_data = {
                "xpow_token": None,
                "headers": None,
                "cookies": None
            }
            data_event = asyncio.Event()

            async def handle_request(request: Request):
                if "__internal/u-card/cards/v4/detail" in request.url:
                    logger.debug(f"✅ Перехвачен API запрос для nm={nm_id}")
                    captured_data["headers"] = dict(request.headers)
                    
                    if "x-pow" in request.headers:
                        captured_data["xpow_token"] = request.headers["x-pow"]
                        logger.debug(f"  x-pow: {request.headers['x-pow'][:50]}...")
                    
                    cookies = await page.context.cookies()
                    captured_data["cookies"] = cookies
                    data_event.set()

            page.on("request", handle_request)

            # ✅ Загружаем страницу (wait_until="load" достаточно)
            url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
            await page.goto(url, wait_until="load", timeout=20000)

            # ✅ Ждём перехвата API запроса
            try:
                await asyncio.wait_for(data_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error(f"❌ API запрос не перехвачен для nm={nm_id} (timeout 10s)")
                return None

            if not captured_data["headers"] or not captured_data["xpow_token"]:
                logger.error(f"❌ Не удалось перехватить данные сессии #{session_num}")
                return None

            # Убираем HTTP/2 псевдо-заголовки
            headers = {
                k: v for k, v in captured_data["headers"].items()
                if not k.startswith(":")
            }

            # Проверяем x-pow
            if "x-pow" not in headers and "X-Pow" not in headers:
                if captured_data["xpow_token"]:
                    headers["x-pow"] = captured_data["xpow_token"]
                else:
                    logger.error(f"❌ x-pow не найден для nm={nm_id}")
                    return None

            session_data = {
                "headers": headers,
                "xpow_token": captured_data["xpow_token"],
                "cookies": captured_data["cookies"],
                "created_at": time.time(),
                "request_count": 0
            }

            logger.info(f"✅ Сессия #{session_num} создана: x-pow={captured_data['xpow_token'][:30]}...")

            return session_data

        except Exception as e:
            logger.exception(f"❌ Ошибка создания сессии #{session_num}: {e}")
            return None

    async def _do_warmup(self) -> bool:
        """
        🔥 ЖЕРТВЕННАЯ СЕССИЯ: создаём и "сжигаем" для прогрева браузера.
        Вызывается ОДИН РАЗ при инициализации.
        """
        self._session_stats["warmup_sessions"] += 1
        warmup_num = self._session_stats["warmup_sessions"]
        
        logger.info(f"🔥 Прогрев #{warmup_num}: создаю жертвенную сессию...")
        
        try:
            # Создаём жертвенную сессию
            warmup_session = await self._create_new_session(143627628, DEFAULT_DEST)
            
            if not warmup_session:
                logger.error("❌ Не удалось создать жертвенную сессию")
                return False
            
            # Делаем 3 запроса на жертвенной сессии (получим Challenge)
            warmup_items = [143627628, 124736264, 9866831]
            
            logger.info(f"🔥 Прогрев #{warmup_num}: делаю 3 тестовых запроса (ожидается Challenge)...")
            
            success_count = 0
            for i, test_nm in enumerate(warmup_items, 1):
                try:
                    headers = warmup_session["headers"].copy()
                    headers["referer"] = f"https://www.wildberries.ru/catalog/{test_nm}/detail.aspx"
                    
                    resp = await self._context.request.get(
                        get_api_url(DEFAULT_DEST, test_nm),
                        headers=headers,
                        timeout=15000
                    )
                    
                    if resp.status == 200:
                        success_count += 1
                        logger.info(f"  🔥 Запрос {i}/3: nm={test_nm} — ✓ (200)")
                    else:
                        logger.warning(f"  🔥 Запрос {i}/3: nm={test_nm} — ✗ ({resp.status})")
                    
                    await asyncio.sleep(0.8)
                    
                except Exception as e:
                    logger.warning(f"  ⚠️ Запрос {i}/3 не удался: {e}")
            
            # Пауза перед созданием рабочей сессии
            await asyncio.sleep(1.0)
            
            logger.info(
                f"✅ Прогрев #{warmup_num} завершён. "
                f"Успешно: {success_count}/3 запросов. Жертвенная сессия использована."
            )

            # Считаем успешным, если хотя бы 2 из 3 запросов прошли
            return success_count >= 2
            
        except Exception as e:
            logger.exception(f"❌ Критическая ошибка прогрева #{warmup_num}: {e}")
            return False

    async def do_warmup_cycle(self) -> bool:
        """
        Публичный метод для прогрева перед циклом мониторинга.
        Сбрасывает флаг warmup_done и делает свежий прогрев.
        """
        logger.info("🔥 Запуск прогрева перед новым циклом мониторинга...")
        self._warmup_done = False
        
        warmup_success = await self._do_warmup()
        self._warmup_done = True
        
        if warmup_success:
            logger.info("✅ Прогрев цикла завершён успешно")
        else:
            logger.warning("⚠️ Прогрев цикла не удался")
        
        return warmup_success

    def get_stats(self) -> Dict:
        """Получить статистику использования сессий."""
        open_pages = len(self._context.pages) if self._context else 0
        return {
            **self._session_stats,
            "current_session_age": time.time() - self._session_created_at if self._current_session else 0,
            "current_session_requests": self._session_request_count,
            "warmup_done": self._warmup_done,
            "open_pages": open_pages,
            "permanent_page": self._permanent_page and not self._permanent_page.is_closed()
        }

    async def get_full_request_data(self, nm_id: int, dest: int) -> Optional[Dict]:
        """
        Получить полные данные для запроса.
        При первом вызове делает прогрев.
        """
        async with self._lock:
            # # ✅ ПРОГРЕВ ПРИ ПЕРВОМ ЗАПРОСЕ ПОСЛЕ ОТКРЫТИЯ БРАУЗЕРА
            # if not self._warmup_done:
            #     logger.info("🔥 Первый запрос после открытия браузера — делаю прогрев")
            #     warmup_success = await self._do_warmup()
            #     self._warmup_done = True
                
            #     if not warmup_success:
            #         logger.warning("⚠️ Прогрев не удался, продолжаю без него")
            
            # ✅ ПРОВЕРЯЕМ НУЖНА ЛИ НОВАЯ РАБОЧАЯ СЕССИЯ
            need_new_session = (
                not self._current_session or
                (time.time() - self._session_created_at) > self._session_ttl or
                self._session_request_count >= self._max_requests_per_session
            )

            if need_new_session:
                if self._current_session:
                    logger.info(
                        f"♻️ Создаю новую сессию (предыдущая: {self._session_request_count} запросов)"
                    )
                
                self._current_session = await self._create_new_session(nm_id, dest)
                
                if not self._current_session:
                    return None
                
                self._session_created_at = time.time()
                self._session_request_count = 0
                await asyncio.sleep(0.5)
            
            # ✅ ИСПОЛЬЗУЕМ РАБОЧУЮ СЕССИЮ
            self._session_request_count += 1
            
            session_age = time.time() - self._session_created_at
            
            logger.debug(
                f"[nm={nm_id}] Сессия: age={session_age:.0f}s, "
                f"req#{self._session_request_count}/{self._max_requests_per_session}"
            )
            
            # ✅ Копируем заголовки и обновляем Referer
            final_headers = self._current_session["headers"].copy()
            final_headers["referer"] = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
            
            return {
                "xpow_token": self._current_session["xpow_token"],
                "headers": final_headers,
                "cookies": self._current_session["cookies"],
                "url": get_api_url(dest, nm_id),
                "timestamp": time.time(),
                "session_age": session_age,
                "session_request_count": self._session_request_count
            }

    async def get_xpow_token(self, nm_id: int, dest: int) -> Optional[str]:
        """Совместимость со старым API."""
        data = await self.get_full_request_data(nm_id, dest)
        return data["xpow_token"] if data else None


# Глобальный экземпляр
_xpow_fetcher: Optional[XPowFetcher] = None
_xpow_fetcher_lock = asyncio.Lock()


async def get_xpow_fetcher() -> XPowFetcher:
    """Получить глобальный экземпляр XPowFetcher."""
    global _xpow_fetcher
    
    # ✅ Быстрая проверка без блокировки
    if _xpow_fetcher is not None:
        return _xpow_fetcher
    
    # ✅ Блокируем для инициализации
    async with _xpow_fetcher_lock:
        # Double-check pattern
        if _xpow_fetcher is None:
            logger.info("🌐 Инициализирую браузер и делаю прогрев...")
            
            _xpow_fetcher = XPowFetcher()
            await _xpow_fetcher.init()
            
            logger.info("🎯 XPowFetcher готов к работе")
    
    return _xpow_fetcher
