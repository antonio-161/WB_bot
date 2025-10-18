import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram import exceptions
from aiogram.types import BotCommand
from config import settings
from services.db import DB, ProductRow
from services.price_fetcher import PriceFetcher
from handlers import (
    plan as plan_h,
    start as start_h,
    products as products_h,
    settings as settings_h,
    region as region_h
)
from decimal import Decimal
from utils.wb_utils import apply_wallet_discount
from constants import DEFAULT_DEST

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Container:
    """Контейнер зависимостей."""
    def __init__(self, db: DB, price_fetcher: PriceFetcher):
        self.db = db
        self.price_fetcher = price_fetcher


async def monitor_loop(container: Container, bot: Bot):
    """Основной цикл мониторинга цен и остатков."""
    poll = settings.POLL_INTERVAL_SECONDS
    hourly_metrics = {"processed": 0, "errors": 0, "notifications": 0}
    cycles = 0
    report_every = max(1, 3600 // poll)

    async def process_product(p: ProductRow, metrics: dict):
        try:
            user = await container.db.get_user(p.user_id)
            dest = user.get("dest", DEFAULT_DEST) if user else DEFAULT_DEST

            # Получаем данные о товаре (цены + остатки + размеры)
            new_data = await container.price_fetcher.get_product_data(p.nm_id, dest=dest)
            if not new_data:
                metrics["errors"] += 1
                logger.warning(f"[nm={p.nm_id}] Не удалось получить данные о товаре")
                return

            # Если есть размеры
            sizes = new_data.get("sizes", [])
            if sizes:
                selected_size = p.selected_size
                if not selected_size:
                    # Пользователь не выбрал размер — пропускаем обработку
                    logger.info(f"[nm={p.nm_id}] Размер не выбран, пропуск")
                    return

                # Находим выбранный размер
                size_data = next((s for s in sizes if s.get("name") == selected_size), None)
                if not size_data:
                    metrics["errors"] += 1
                    logger.warning(f"[nm={p.nm_id}] Выбранный размер '{selected_size}' не найден")
                    return

                price_info = size_data.get("price", {})
                stocks = size_data.get("stocks", [])
            else:
                # Товар без размеров
                price_info = new_data.get("price", {})
                stocks = new_data.get("stocks", [])

            new_basic = Decimal(str(price_info.get("basic", 0)))
            new_prod = Decimal(str(price_info.get("product", 0)))
            qty_total = sum(stock.get("qty", 0) for stock in stocks)
            out_of_stock = qty_total == 0

            # Обновляем название товара, если нужно
            if p.name_product == "Загрузка..." and new_data.get("name"):
                await container.db.update_product_name(p.id, new_data["name"])

            old_prod = p.last_product_price
            old_qty = getattr(p, "last_qty", None)
            notify_price = old_prod is not None and new_prod < old_prod
            notify_stock = old_qty is not None and old_qty > 0 and out_of_stock

            # Сохраняем цены и остатки
            await container.db.update_prices_and_stock(
                p.id, new_basic, new_prod, qty_total, out_of_stock
            )
            metrics["processed"] += 1

            # Формируем уведомление
            msg = ""
            if notify_price:
                discount = user.get("discount_percent", 0) if user else 0
                price_no_wallet = float(new_prod)
                price_with_wallet = apply_wallet_discount(price_no_wallet, discount)
                old_price = float(old_prod)
                diff = old_price - price_no_wallet
                diff_percent = (diff / old_price) * 100

                msg += (
                    f"🔔 <b>Цена снизилась!</b>\n\n"
                    f"📦 {p.name_product}\n"
                    f"🔗 <a href='{p.url_product}'>Открыть товар</a>\n\n"
                    f"💰 <b>Новая цена:</b> {price_no_wallet:.2f} ₽\n"
                )
                if discount > 0:
                    msg += f"💳 <b>С WB кошельком ({discount}%):</b> {price_with_wallet:.2f} ₽\n"
                msg += (
                    f"📉 <b>Было:</b> {old_price:.2f} ₽\n"
                    f"✅ <b>Экономия:</b> {diff:.2f} ₽ ({diff_percent:.1f}%)\n"
                )

            if notify_stock:
                msg += (
                    f"⚠️ <b>Товар закончился!</b>\n\n"
                    f"📦 {p.name_product}\n"
                    f"🔗 <a href='{p.url_product}'>Открыть товар</a>\n"
                )

            if msg:
                try:
                    await bot.send_message(
                        p.user_id,
                        msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    metrics["notifications"] += 1
                    logger.info(f"Отправлено уведомление пользователю {p.user_id} по nm={p.nm_id}")
                except exceptions.TelegramForbiddenError:
                    logger.warning(f"Пользователь {p.user_id} заблокировал бота")
                except exceptions.TelegramBadRequest as e:
                    logger.warning(f"Ошибка отправки пользователю {p.user_id}: {e}")
                    metrics["errors"] += 1
                except Exception as e:
                    logger.exception(f"Неожиданная ошибка при отправке уведомления: {e}")
                    metrics["errors"] += 1

        except Exception as e:
            logger.exception(f"[nm={p.nm_id}] Ошибка при обработке товара: {e}")
            metrics["errors"] += 1

    while True:
        try:
            logger.info("Начинаю цикл мониторинга...")
            products = await container.db.all_products()
            if not products:
                logger.info("Нет товаров для мониторинга")
                await asyncio.sleep(poll)
                continue

            metrics = {"processed": 0, "errors": 0, "notifications": 0}

            batch_size = 50
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]
                tasks = [asyncio.create_task(process_product(p, metrics)) for p in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
                if i + batch_size < len(products):
                    await asyncio.sleep(5)

            for k in metrics:
                hourly_metrics[k] += metrics[k]
            cycles += 1

            logger.info(
                f"Цикл завершён: обработано={metrics['processed']}, "
                f"ошибок={metrics['errors']}, уведомлений={metrics['notifications']}"
            )

            if cycles >= report_every:
                report = (
                    "📊 <b>Отчёт за последний час</b>\n\n"
                    f"✅ Обработано товаров: {hourly_metrics['processed']}\n"
                    f"❌ Ошибок: {hourly_metrics['errors']}\n"
                    f"🔔 Уведомлений отправлено: {hourly_metrics['notifications']}\n\n"
                    f"⏰ Интервал проверки: {poll} сек"
                )
                try:
                    await bot.send_message(settings.ADMIN_CHAT_ID, report, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Не удалось отправить отчёт админу: {e}")
                hourly_metrics = {"processed": 0, "errors": 0, "notifications": 0}
                cycles = 0

            await asyncio.sleep(poll)

        except Exception as e:
            logger.exception(f"Критическая ошибка в monitor_loop: {e}")
            await asyncio.sleep(poll)


async def main():
    """Основная функция запуска бота."""
    logger.info("🚀 Запуск бота...")

    # Создаём объекты
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    db = DB(str(settings.DATABASE_DSN))
    await db.connect()
    logger.info("✅ Подключение к БД установлено")

    fetcher = PriceFetcher()
    container = Container(db=db, price_fetcher=fetcher)

    # Добавляем routers
    dp.include_router(start_h.router)
    dp.include_router(plan_h.router)
    dp.include_router(products_h.router)
    dp.include_router(settings_h.router)
    dp.include_router(region_h.router)

    # Dependency injection для handlers
    dp["db"] = db
    dp["price_fetcher"] = fetcher

    # Запускаем монитор в фоне
    monitor_task = asyncio.create_task(monitor_loop(container, bot))
    logger.info("✅ Монитор цен запущен")

    # Установка команд бота
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Главное меню"),
    ])
    logger.info("✅ Команды бота установлены")

    try:
        logger.info("✅ Бот готов к работе")
        await dp.start_polling(
            bot, allowed_updates=["message", "callback_query"]
        )
    except KeyboardInterrupt:
        logger.info("⛔ Получен сигнал остановки")
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        
        await db.close()
        await bot.session.close()
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка через Ctrl+C")
