"""
Модуль для определения dest по адресу ПВЗ через Playwright.
Основан на wb_dest.py скрипте.
"""
import logging
import aiohttp
from playwright.async_api import async_playwright
from typing import Optional

logger = logging.getLogger(__name__)


async def get_dest_by_address(address: str) -> Optional[int]:
    """
    Поиск ПВЗ Wildberries по адресу и получение dest.

    Args:
        address: Адрес ПВЗ как в приложении/сайте WB

    Returns:
        int: dest код региона
        None: если не удалось определить
    """
    logger.info(f"Начинаю поиск dest для адреса: {address}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            page = await browser.new_page()

            logger.debug("Открываю страницу Wildberries...")
            await page.goto(
                "https://www.wildberries.ru/services/besplatnaya-dostavka?",
                wait_until="domcontentloaded",
                timeout=30000
            )
            await page.wait_for_timeout(5000)

            logger.debug("Ищу поле ввода адреса...")
            input_box = await page.wait_for_selector(
                "input.map-search__input",
                timeout=20000
            )

            logger.debug(f"Ввожу адрес: {address}")
            await input_box.fill(address)
            await page.wait_for_timeout(1000)

            logger.debug("Нажимаю кнопку 'Найти'...")
            await page.click("button.map-search__confirm-btn")
            await page.wait_for_timeout(2000)

            logger.debug("Жду список ПВЗ...")
            await page.wait_for_selector(
                "div.address-item.j-poo-option",
                timeout=60000
            )

            # Берем первый адрес и читаем его data-id
            element = await page.query_selector("div.address-item.j-poo-option")
            data_id = await element.get_attribute("data-id")
            logger.info(f"Найден ПВЗ с ID: {data_id}")

            await browser.close()

        # Получаем JSON с сервера
        json_url = f"https://www.wildberries.ru/webapi/spa/poo/{data_id}/show"
        logger.debug(f"Получаю JSON с {json_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(json_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    dest = data.get("value", {}).get("dest")

                    if dest:
                        logger.info(f"✅ Успешно получен dest={dest} для адреса: {address}")
                        return int(dest)
                    else:
                        logger.warning(f"dest не найден в JSON ответе для {address}")
                        return None
                else:
                    logger.error(f"Ошибка HTTP {resp.status} при запросе JSON")
                    return None

    except Exception as e:
        logger.exception(f"Ошибка при определении dest для адреса '{address}': {e}")
        return None
