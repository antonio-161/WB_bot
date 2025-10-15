import asyncio
import logging
import random
import time
from typing import Dict, Optional
import requests

from constants import DEFAULT_DEST


logger = logging.getLogger(__name__)


def get_price_sync(
        nm_id: int, dest: int | None = None, spp: int = 30
) -> Dict[str, float | str]:
    if dest is None:
        dest = DEFAULT_DEST

    url = (
        "https://card.wb.ru/cards/v4/detail"
        f"?appType=1&curr=rub&dest={dest}&spp={spp}&hide_dtype=11"
        f"&ab_testing=false&lang=ru&nm={nm_id}"
    )

    for attempt in range(3):
        try:
            r = requests.get(url, timeout=(5, 10))
            r.raise_for_status()
            js = r.json()
            products = js.get("products", [])
            if not products:
                raise ValueError(f"[nm={nm_id}] Пустой ответ от WB")

            data = products[0]
            p = data["sizes"][0]["price"]

            return {
                "basic": p["basic"] / 100.0,
                "product": p["product"] / 100.0,
                "name": data.get("name", f"Товар {nm_id}")
            }

        except (requests.exceptions.RequestException, ValueError) as e:
            if attempt < 2:
                sleep_time = 2 ** attempt
                logger.warning(
                    f"[nm={nm_id}] Ошибка запроса ({e}), повтор через {sleep_time}s"
                )
                time.sleep(sleep_time)
                continue
            raise


class PriceFetcher:
    """
    Асинхронный интерфейс для получения цены с rate limiting.
    """

    def __init__(self, concurrency: int = 10, delay_range=(0.2, 1.0)):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.delay_range = delay_range

    async def get_price(
        self, nm_id: int, dest: Optional[int] = None
    ) -> Optional[Dict[str, float]]:
        """
        Асинхронное получение цены с контролем параллельности,
        случайной паузой и защитой от зависаний.
        """
        async with self.semaphore:
            # случайная пауза, чтобы не “бомбить” WB
            await asyncio.sleep(random.uniform(*self.delay_range))

            loop = asyncio.get_running_loop()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, get_price_sync, nm_id, dest),
                    timeout=15,  # общий лимит на всю операцию
                )
                return result
            except asyncio.TimeoutError:
                logger.error(f"[nm={nm_id}] Таймаут при получении цены")
                return None
            except Exception as e:
                logger.error(f"[nm={nm_id}] Ошибка в get_price: {e}")
                return None
