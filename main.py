import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram import exceptions
from aiogram.types import BotCommand
from config import settings
from services.db import DB
from services.price_fetcher import PriceFetcher
from handlers import (
    plan as plan_h,
    start as start_h,
    products as products_h,
    settings as settings_h
)
from decimal import Decimal
from utils.wb_utils import apply_wallet_discount
from constants import DEFAULT_DEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Dependency injection container (simple)
class Container:
    """Контейнер зависимостей."""
    def __init__(self, db: DB, price_fetcher: PriceFetcher):
        self.db = db
        self.price_fetcher = price_fetcher


async def monitor_loop(container: Container, bot: Bot):
    poll = settings.POLL_INTERVAL_SECONDS

    # накопительные метрики за час
    hourly_metrics = {"processed": 0, "errors": 0, "notifications": 0}
    cycles = 0
    report_every = 3600 // poll  # сколько циклов примерно в час

    async def process_product(p, metrics):
        try:
            user = await container.db.get_user(p.user_id)
            dest = user.get("dest", DEFAULT_DEST) if user else DEFAULT_DEST

            new = await container.price_fetcher.get_price(p.nm_id, dest=dest)
            if not new:
                metrics["errors"] += 1
                return

            old_prod = p.last_product_price
            new_prod = Decimal(str(new["product"]))
            new_basic = Decimal(str(new["basic"]))

            notify = old_prod is not None and new_prod < old_prod

            await container.db.update_prices(p.id, new_basic, new_prod)
            metrics["processed"] += 1

            if notify and user:
                discount = user.get("discount_percent", 0)
                price_no_wallet = float(new_prod)
                price_with_wallet = apply_wallet_discount(
                    price_no_wallet, discount
                )

                msg = (
                    f"Цена снизилась для товара {p.name}!\n"
                    f"Ссылка: {p.url}\n"
                    f"Цена без WB кошелька: {price_no_wallet:.2f} ₽\n"
                    f"Цена с WB кошельком ({discount}%): {price_with_wallet:.2f} ₽\n"
                    f"Раньше: {float(old_prod):.2f} ₽ → Сейчас: {price_no_wallet:.2f} ₽"
                )

                try:
                    await bot.send_message(p.user_id, msg)
                    metrics["notifications"] += 1
                except exceptions.TelegramBadRequest:
                    logger.warning(
                        "Не смог отправить сообщение пользователю %s",
                        p.user_id
                    )
                    metrics["errors"] += 1

        except Exception as e:
            logger.exception(
                "Ошибка при обработке товара nm=%s: %s", p.nm_id, e
            )
            metrics["errors"] += 1

    while True:
        try:
            products = await container.db.all_products()

            metrics = {"processed": 0, "errors": 0, "notifications": 0}
            tasks = [
                asyncio.create_task(process_product(p, metrics)) for p in products
                ]
            if tasks:
                await asyncio.gather(*tasks)

            # обновляем накопительные метрики
            for k in metrics:
                hourly_metrics[k] += metrics[k]

            cycles += 1

            # логируем метрики цикла
            logger.info(
                "Цикл завершён: обработано=%s, ошибок=%s, уведомлений=%s",
                metrics["processed"],
                metrics["errors"],
                metrics["notifications"]
            )

            # раз в час отправляем отчёт админу
            if cycles >= report_every:
                report = (
                    "📊 Отчёт за последний час:\n"
                    f"Обработано товаров: {hourly_metrics['processed']}\n"
                    f"Ошибок: {hourly_metrics['errors']}\n"
                    f"Уведомлений отправлено: {hourly_metrics['notifications']}"
                )
                try:
                    await bot.send_message(settings.ADMIN_CHAT_ID, report)
                except Exception as e:
                    logger.error("Не удалось отправить отчёт админу: %s", e)

                # сбрасываем счётчики
                hourly_metrics = {
                    "processed": 0,
                    "errors": 0,
                    "notifications": 0
                    }
                cycles = 0

            await asyncio.sleep(poll)

        except Exception:
            logger.exception("Ошибка в monitor_loop, жду и продолжаю.")
            await asyncio.sleep(poll)


async def main():
    # Создаём объекты
    bot = Bot(token=settings.BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    db = DB(settings.DATABASE_DSN)
    await db.connect()

    fetcher = PriceFetcher()
    container = Container(db=db, price_fetcher=fetcher)

    # Добавляем routers
    dp.include_router(plan_h.router)
    dp.include_router(start_h.router)
    dp.include_router(products_h.router)
    dp.include_router(settings_h.router)

    # Запускаем монитор в фоне
    loop = asyncio.get_event_loop()
    loop.create_task(monitor_loop(container, bot))

    dp["db"] = db
    dp["price_fetcher"] = fetcher

    # Установка команд
    await bot.set_my_commands([
        BotCommand(command="start", description="Старт"),
        BotCommand(command="add", description="Добавить товар"),
        BotCommand(command="list", description="Список отслеживаемых"),
        BotCommand(command="setdiscount", description="Установить скидку WB"),
        BotCommand(command="remove", description="Удалить товар"),
    ])

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
