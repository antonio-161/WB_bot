import asyncio
import logging
import random
from typing import Dict, Optional
import aiohttp
from constants import DEFAULT_DEST
from services.xpow_fetcher import get_xpow_fetcher
from utils.loggers import challenge_logger
from utils.cache import cached, product_cache
from utils.decorators import retry_on_error
from utils.error_tracker import get_error_tracker, ErrorType

logger = logging.getLogger(__name__)


class PriceFetchError(Exception):
    """Ошибка при получении данных о товаре."""
    pass


async def get_product_data_async(
    session: aiohttp.ClientSession,
    nm_id: int,
    dest: Optional[int] = None,
    browser_request_data: Optional[Dict] = None,
) -> Dict:
    """Получаем все данные о товаре с правильными заголовками."""
    if dest is None:
        dest = DEFAULT_DEST

    url = (
        f"https://u-card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest={dest}"
        f"&spp=30&hide_dtype=11&ab_testing=false&lang=ru&nm={nm_id}"
    )

    # Подготовка заголовков
    if browser_request_data:
        headers = browser_request_data["headers"].copy()
        session_age = browser_request_data.get("session_age", 0)
        session_request_count = browser_request_data.get(
            "session_request_count", 0
        )
    else:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Referer": f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
        }
        session_age = 0
        session_request_count = 0

    for attempt in range(3):
        try:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    raise PriceFetchError(f"HTTP {resp.status} для nm={nm_id}")

                # Проверяем challenge
                response_xpow = resp.headers.get("x-pow", "")
                has_challenge = "challenge=" in response_xpow

                data = await resp.json()
                products = data.get("products", [])

                if not products:
                    raise PriceFetchError(f"Пустой ответ для nm={nm_id}")

                # Подсчёт остатков
                total_qty = sum(
                    stock.get("qty", 0)
                    for size in products[0].get("sizes", [])
                    for stock in size.get("stocks", [])
                )

                # Единый лог с результатом
                status = "CHALLENGE" if has_challenge else "OK"
                challenge_logger.info(
                    f"{status} | nm={nm_id} | qty={total_qty:4d} | "
                    f"session_age={session_age:.0f}s | "
                    f"session_req#{session_request_count}"
                )

                # Короткий лог в основной logger
                challenge_icon = "⚠️" if has_challenge else "✓"
                logger.info(
                    f"[nm={nm_id}] {challenge_icon} qty={total_qty:4d} | "
                    f"req#{session_request_count}"
                )

                # Отклоняем данные с challenge
                # if has_challenge:
                #     raise PriceFetchError(f"Challenge received for nm={nm_id}")

                return products[0]

        except aiohttp.ClientError as e:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
                continue
            raise PriceFetchError(f"Не удалось получить данные: {e}")


class PriceFetcher:
    """Менеджер для получения цен и остатков с rate limiting."""

    def __init__(
            self,
            concurrency: int = 10,
            delay_range=(0.3, 0.8),
            use_xpow: bool = True
    ):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay_range = delay_range
        self._session: Optional[aiohttp.ClientSession] = None
        self.use_xpow = use_xpow
        self._xpow_fetcher = None
        self.error_tracker = get_error_tracker()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get_xpow_fetcher(self):
        """Получить XPowFetcher если нужно."""
        if self.use_xpow and self._xpow_fetcher is None:
            self._xpow_fetcher = await get_xpow_fetcher()
        return self._xpow_fetcher

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @retry_on_error(max_attempts=3, delay=2, exceptions=(PriceFetchError,))
    @cached(ttl=300, cache_instance=product_cache)
    async def get_product_data(
        self, nm_id: int, dest: Optional[int] = None
    ) -> Optional[Dict]:
        """Получение данных с правильными браузерными заголовками."""

        async with self.semaphore:
            await asyncio.sleep(random.uniform(*self.delay_range))

            # ✅ ПОЛУЧАЕМ ПОЛНЫЕ ДАННЫЕ ИЗ БРАУЗЕРА
            browser_request_data = None
            if self.use_xpow:
                try:
                    xpow_fetcher = await self._get_xpow_fetcher()
                    if xpow_fetcher:
                        # ✅ ЖДЁМ ЗАВЕРШЕНИЯ ПРОГРЕВА (если ещё не готов)
                        if not xpow_fetcher._warmup_done:
                            logger.info(f"[nm={nm_id}] ⏳ Жду завершения прогрева...")

                            # Ждём максимум 30 секунд
                            for i in range(300):
                                if xpow_fetcher._warmup_done:
                                    logger.info(f"[nm={nm_id}] ✅ Прогрев завершён, продолжаю")
                                    break
                                await asyncio.sleep(0.1)

                            if not xpow_fetcher._warmup_done:
                                logger.warning(f"[nm={nm_id}] ⚠️ Прогрев не завершился за 30с, продолжаю без x-pow")

                        # Получаем данные сессии
                        browser_request_data = await xpow_fetcher.get_full_request_data(
                            nm_id,
                            dest or DEFAULT_DEST
                        )

                        if browser_request_data:
                            logger.debug(
                                f"[nm={nm_id}] Заголовки: {len(browser_request_data.get('headers', {}))} шт."
                            )

                except Exception as e:
                    logger.warning(f"[nm={nm_id}] Не удалось получить браузерные заголовки: {e}")

            try:
                session = await self._get_session()

                # ✅ ПЕРЕДАЁМ ПОЛНЫЕ ДАННЫЕ ИЗ БРАУЗЕРА
                data = await asyncio.wait_for(
                    get_product_data_async(session, nm_id, dest, browser_request_data),
                    timeout=20
                )

                if not data:
                    return None

                # Обрабатываем ответ
                result = {
                    "name": data.get("name", f"Товар {nm_id}"),
                    "sizes": []
                }

                for s in data.get("sizes", []):
                    price_data = s.get("price", {})

                    size_info = {
                        "name": s.get("name", ""),
                        "origName": s.get("origName", ""),
                        "price": {
                            "basic": int(price_data.get("basic", 0)) // 100,
                            "product": int(price_data.get("product", 0)) // 100,
                        },
                        "stocks": [{"qty": stock.get("qty", 0)} for stock in s.get("stocks", [])]
                    }
                    result["sizes"].append(size_info)

                self.error_tracker.track_success()
                return result

            except (KeyError, ValueError, IndexError) as e:
                self.error_tracker.track_error(
                    ErrorType.PARSE_ERROR,
                    nm_id=nm_id,
                    details=str(e)
                )
                logger.error(f"[nm={nm_id}] Ошибка парсинга: {e}")
                return None

            except Exception as e:
                self.error_tracker.track_error(
                    ErrorType.UNKNOWN,
                    nm_id=nm_id,
                    details=str(e)
                )
                logger.exception(f"[nm={nm_id}] Неизвестная ошибка: {e}")
                return None

    async def get_products_batch(self, nm_ids: list[int], dest: Optional[int] = None) -> Dict[int, Optional[Dict]]:
        """Получить данные о нескольких товарах в одном запросе."""
        tasks = [self.get_product_data(nm_id, dest) for nm_id in nm_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {nm_id: res if not isinstance(res, Exception) else None for nm_id, res in zip(nm_ids, results)}
