import asyncio
import logging
import random
from typing import Dict, Optional
import aiohttp
from constants import DEFAULT_DEST
from utils.cache import product_cache
from utils.decorators import retry_on_error

logger = logging.getLogger(__name__)


class PriceFetchError(Exception):
    """Ошибка при получении данных о товаре."""
    pass


async def get_product_data_async(
    session: aiohttp.ClientSession,
    nm_id: int,
    dest: Optional[int] = None,
    xpow_token: Optional[str] = None,
) -> Dict:
    """Получаем все данные о товаре: цены, остатки, размеры."""
    if dest is None:
        dest = DEFAULT_DEST

    url = (
        f"https://u-card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest={dest}"
        f"&spp=30&hide_dtype=11&ab_testing=false&lang=ru&nm={nm_id}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
        "Origin": "https://www.wildberries.ru",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
    }
    
    # Добавляем x-pow если есть
    if xpow_token:
        headers["x-pow"] = xpow_token
        logger.debug(f"[nm={nm_id}] Используем x-pow токен")

    for attempt in range(3):
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise PriceFetchError(f"HTTP {resp.status} для nm={nm_id}")
                data = await resp.json()
                products = data.get("products", [])
                if not products:
                    raise PriceFetchError(f"Пустой ответ для nm={nm_id}")
                return products[0]  # возвращаем первый товар
        except aiohttp.ClientError as e:
            if attempt < 2:
                sleep_time = 2 ** attempt + random.uniform(0, 1)
                logger.warning(f"[nm={nm_id}] Ошибка запроса ({e}), повтор через {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
                continue
            raise PriceFetchError(f"Не удалось получить данные после 3 попыток: {e}")
        except (KeyError, IndexError, ValueError) as e:
            raise PriceFetchError(f"Ошибка парсинга данных для nm={nm_id}: {e}")


class PriceFetcher:
    """Менеджер для получения цен и остатков с rate limiting."""

    def __init__(self, concurrency: int = 10, delay_range=(0.3, 0.8), use_xpow: bool = True):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay_range = delay_range
        self._session: Optional[aiohttp.ClientSession] = None
        self.use_xpow = use_xpow
        self._xpow_fetcher = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _get_xpow_fetcher(self):
        """Получить XPowFetcher если нужно."""
        if self.use_xpow and self._xpow_fetcher is None:
            from services.xpow_fetcher import get_xpow_fetcher
            self._xpow_fetcher = await get_xpow_fetcher()
        return self._xpow_fetcher

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    @retry_on_error(max_attempts=3, delay=2, exceptions=(PriceFetchError,))
    async def get_product_data(
        self, nm_id: int, dest: Optional[int] = None
    ) -> Optional[Dict]:
        """Получение данных с кэшированием."""

        # Проверяем кэш
        cache_key = f"product_{nm_id}_{dest or DEFAULT_DEST}"
        cached = product_cache.get(cache_key)
        
        if cached:
            logger.debug(f"[nm={nm_id}] Данные из кэша")
            return cached
    
        async with self.semaphore:
            await asyncio.sleep(random.uniform(*self.delay_range))
            
            xpow_token = None
            if self.use_xpow:
                try:
                    xpow_fetcher = await self._get_xpow_fetcher()
                    if xpow_fetcher:
                        # Пробуем основной метод
                        xpow_token = await xpow_fetcher.get_xpow_token(nm_id, dest or DEFAULT_DEST)
                        
                        # Если не получилось - пробуем simple метод
                        if not xpow_token:
                            logger.debug(f"[nm={nm_id}] Пробуем simple метод получения x-pow")
                            xpow_token = await xpow_fetcher.get_xpow_simple(nm_id, dest or DEFAULT_DEST)
                        
                        if xpow_token:
                            logger.debug(f"[nm={nm_id}] X-pow токен получен")
                        else:
                            logger.warning(f"[nm={nm_id}] X-pow токен не получен, запрос без токена")
                except Exception as e:
                    logger.warning(f"[nm={nm_id}] Не удалось получить x-pow токен: {e}")
            
            try:
                session = await self._get_session()
                data = await asyncio.wait_for(
                    get_product_data_async(session, nm_id, dest, xpow_token), 
                    timeout=20
                )

                # Подготавливаем удобный словарь
                result = {
                    "name": data.get("name", f"Товар {nm_id}"),
                    "sizes": []
                }

                # Обрабатываем размеры
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

                if result:
                    product_cache.set(cache_key, result)

                return result

            except Exception as e:
                logger.error(f"[nm={nm_id}] Ошибка при получении данных: {e}")
                return None

    async def get_products_batch(self, nm_ids: list[int], dest: Optional[int] = None) -> Dict[int, Optional[Dict]]:
        tasks = [self.get_product_data(nm_id, dest) for nm_id in nm_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {nm_id: res if not isinstance(res, Exception) else None for nm_id, res in zip(nm_ids, results)}
