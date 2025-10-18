import asyncio
import logging
import random
from typing import Dict, Optional
import aiohttp
from decimal import Decimal
from constants import DEFAULT_DEST

logger = logging.getLogger(__name__)


class PriceFetchError(Exception):
    """Ошибка при получении данных о товаре."""
    pass


async def get_product_data_async(
    session: aiohttp.ClientSession,
    nm_id: int,
    dest: Optional[int] = None,
) -> Dict:
    """Получаем все данные о товаре: цены, остатки, размеры."""
    if dest is None:
        dest = DEFAULT_DEST

    url = (
        f"https://u-card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest={dest}"
        f"&spp=30&hide_dtype=11&ab_testing=false&lang=ru&nm={nm_id}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36",
        "Referer": f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
        "Origin": "https://www.wildberries.ru",
    }

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

    def __init__(self, concurrency: int = 10, delay_range=(0.3, 0.8)):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay_range = delay_range
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_product_data(
        self, nm_id: int, dest: Optional[int] = None
    ) -> Optional[Dict]:
        """Получение цены, остатка и размеров одним запросом."""
        async with self.semaphore:
            await asyncio.sleep(random.uniform(*self.delay_range))
            try:
                session = await self._get_session()
                data = await asyncio.wait_for(get_product_data_async(session, nm_id, dest), timeout=20)

                # Подготавливаем удобный словарь
                result = {
                    "name": data.get("name", f"Товар {nm_id}"),
                    "sizes": []
                }

                for s in data.get("sizes", []):
                    size_info = {
                        "name": s.get("name"),
                        "origName": s.get("origName"),
                        "price": {
                            "basic": Decimal(str(s.get("price", {}).get("basic", 0))) / 100,
                            "product": Decimal(str(s.get("price", {}).get("product", 0))) / 100,
                        },
                        "stocks": [{"qty": stock.get("qty", 0)} for stock in s.get("stocks", [])]
                    }
                    result["sizes"].append(size_info)

                # Если товар без размеров, создаем виртуальный размер
                if not result["sizes"]:
                    price_data = data.get("price", {})
                    stocks_data = data.get("stocks", [])
                    result["price"] = {
                        "basic": Decimal(str(price_data.get("basic", 0))) / 100,
                        "product": Decimal(str(price_data.get("product", 0))) / 100
                    }
                    result["stocks"] = [{"qty": stock.get("qty", 0)} for stock in stocks_data]

                return result

            except Exception as e:
                logger.error(f"[nm={nm_id}] Ошибка при получении данных: {e}")
                return None

    async def get_products_batch(self, nm_ids: list[int], dest: Optional[int] = None) -> Dict[int, Optional[Dict]]:
        tasks = [self.get_product_data(nm_id, dest) for nm_id in nm_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {nm_id: res if not isinstance(res, Exception) else None for nm_id, res in zip(nm_ids, results)}
