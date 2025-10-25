import asyncio
from datetime import datetime, timedelta
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, BaseMiddleware, Dispatcher
from aiogram import exceptions
from aiogram.types import BotCommand
from config import settings
from services.container import Container
from services.db import DB
from services.price_fetcher import PriceFetcher
from handlers import (
    plan as plan_h,
    start as start_h,
    products as products_h,
    settings as settings_h,
    region as region_h,
    stats as stats_h,
    onboarding as onboarding_h,
    admin as admin_h
)
from utils.error_tracker import get_error_tracker
from utils.health_monitor import get_health_monitor, HealthStatus
from utils.rate_limiter import RateLimitMiddleware
from utils.wb_utils import apply_wallet_discount
from constants import DEFAULT_DEST
from models import ProductRow

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DependencyInjectionMiddleware(BaseMiddleware):
    """
    Middleware для автоматической инъекции репозиториев в handlers.
    
    Зачем: Handlers автоматически получают нужные репозитории как аргументы.
    """
    
    def __init__(self, container: Container):
        super().__init__()
        self.container = container
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Добавляем репозитории в data (они будут доступны в handlers)
        data["user_repo"] = self.container.get_user_repo()
        data["product_repo"] = self.container.get_product_repo()
        data["price_history_repo"] = self.container.get_price_history_repo()
        
        # Также добавляем сам контейнер (для доступа к другим зависимостям)
        data["container"] = self.container
        
        # Для обратной совместимости (пока переписываете handlers)
        data["db"] = self.container.db
        data["price_fetcher"] = self.container.price_fetcher
        
        return await handler(event, data)


async def monitor_loop(container: Container, bot: Bot):
    """Основной цикл мониторинга цен и остатков."""
    poll = settings.POLL_INTERVAL_SECONDS
    hourly_metrics = {"processed": 0, "errors": 0, "notifications": 0}
    cycles = 0
    report_every = max(1, 3600 // poll)
    error_tracker = get_error_tracker()

    # Регистрируем callback для алертов админу
    async def send_alert_to_admin(alert_data: Dict):
        """Отправка алерта администратору."""
        try:
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                alert_data['message'],
                parse_mode="HTML"
            )
            logger.info(f"Alert sent to admin: {alert_data['severity']}")
        except Exception as e:
            logger.exception(f"Failed to send alert to admin: {e}")

    error_tracker.register_alert_callback(send_alert_to_admin)

    async def process_product(p: ProductRow, metrics: dict[str, int]):
        """Обрабатываем один товар."""
        try:
            user = await container.db.get_user(p.user_id)
            dest = user.get("dest", DEFAULT_DEST) if user else DEFAULT_DEST

            # Получаем данные о товаре (цены + остатки + размеры)
            new_data = await container.price_fetcher.get_product_data(p.nm_id, dest=dest)
            if not new_data:
                metrics["errors"] += 1
                logger.warning(f"[nm={p.nm_id}] Не удалось получить данные о товаре")
                return

            sizes = new_data.get("sizes", [])

            # Определяем, есть ли реальные размеры (например S, M, XL)
            has_real_sizes = any(s.get("name") not in ("", "0", None) for s in sizes)

            # --- ТОВАР С РАЗМЕРАМИ ---
            if has_real_sizes:
                selected_size = p.selected_size
                if not selected_size:
                    # Пользователь не выбрал размер — пропускаем обработку
                    logger.info(f"[nm={p.nm_id}] Размер не выбран, пропуск (ожидание выбора пользователем)")
                    return

                # Находим выбранный размер
                size_data = next((s for s in sizes if s.get("name") == selected_size), None)
                if not size_data:
                    metrics["errors"] += 1
                    logger.warning(f"[nm={p.nm_id}] Выбранный размер '{selected_size}' не найден среди {len(sizes)} вариантов")
                    return

                price_info = size_data.get("price", {})
                stocks = size_data.get("stocks", [])

            # --- ТОВАР БЕЗ РЕАЛЬНЫХ РАЗМЕРОВ ---
            else:

                size_data = sizes[0] if sizes else {}
                price_info = size_data.get("price", new_data.get("price", {}))
                stocks = size_data.get("stocks", new_data.get("stocks", []))

                if not price_info:
                    metrics["errors"] += 1
                    logger.warning(f"[nm={p.nm_id}] Нет данных о цене (товар без размеров)")
                    return

            # --- ОБЩИЕ ДАННЫЕ ---
            new_basic = price_info.get("basic", 0)
            new_prod = price_info.get("product", 0)
            qty_total = sum(stock.get("qty", 0) for stock in stocks)
            out_of_stock = qty_total == 0

            # Обновляем название товара, если нужно
            if p.name_product == "Загрузка..." and new_data.get("name"):
                await container.db.update_product_name(p.id, new_data["name"])

            old_prod = p.last_product_price
            old_qty = getattr(p, "last_qty", None)

            # --- Проверка уведомлений ---
            notify_price = False
            if old_prod is not None and new_prod < old_prod:
                if p.notify_mode == "percent":
                    percent_drop = ((old_prod - new_prod) / old_prod) * 100
                    notify_price = percent_drop >= p.notify_value
                elif p.notify_mode == "threshold":
                    notify_price = new_prod <= p.notify_value
                else:
                    notify_price = True

            # Проверка уведомлений о наличии (только для basic/pro)
            user_plan = user.get("plan", "plan_free") if user else "plan_free"
            notify_stock_out = False
            notify_stock_in = False

            if user_plan in ["plan_basic", "plan_pro"]:
                # Товар закончился
                if old_qty is not None and old_qty > 0 and out_of_stock:
                    notify_stock_out = True
                
                # Товар появился
                if old_qty is not None and old_qty == 0 and not out_of_stock and qty_total > 0:
                    notify_stock_in = True

            # --- Сохраняем новые данные ---
            await container.db.update_prices_and_stock(
                p.id, new_basic, new_prod, qty_total, out_of_stock
            )

            # Добавляем запись в историю при изменении цены
            if old_prod is None or new_prod != old_prod:
                await container.db.add_price_history(p.id, new_basic, new_prod, qty_total)

            metrics["processed"] += 1

            # --- Формируем уведомления ---
            msg = ""
            if notify_price:
                discount = user.get("discount_percent", 0) if user else 0
                
                # Расчёт цен с учётом скидки
                old_price_display = old_prod
                new_price_display = new_prod
                
                if discount > 0:
                    old_price_display = apply_wallet_discount(old_prod, discount)
                    new_price_display = apply_wallet_discount(new_prod, discount)
                
                diff = old_price_display - new_price_display
                diff_percent = (diff / old_price_display) * 100 if old_price_display > 0 else 0

                msg += (
                    f"🔔 <b>Цена снизилась!</b>\n\n"
                    f"📦 {p.display_name}\n"
                    f"🔗 <a href='{p.url_product}'>Открыть товар</a>\n\n"
                )
                
                if discount > 0:
                    msg += (
                        f"💳 <b>Цена с WB кошельком ({discount}%):</b>\n"
                        f"✅ <b>Сейчас:</b> {new_price_display} ₽\n"
                        f"📉 <b>Было:</b> {old_price_display} ₽\n"
                        f"💰 <b>Экономия:</b> {diff} ₽ ({diff_percent:.1f}%)\n\n"
                        f"<i>Без кошелька: {new_prod} ₽ (было {old_prod} ₽)</i>\n"
                    )
                else:
                    msg += (
                        f"💰 <b>Новая цена:</b> {new_price_display} ₽\n"
                        f"📉 <b>Было:</b> {old_price_display} ₽\n"
                        f"✅ <b>Экономия:</b> {diff} ₽ ({diff_percent:.1f}%)\n"
                    )

            if notify_stock_out:
                msg += (
                    f"\n⚠️ <b>Товар закончился!</b>\n\n"
                    f"📦 {p.display_name}\n"
                    f"🔗 <a href='{p.url_product}'>Открыть товар</a>\n"
                )

            if notify_stock_in:
                msg += (
                    f"\n✅ <b>Товар снова в наличии!</b>\n\n"
                    f"📦 {p.display_name}\n"
                    f"🔗 <a href='{p.url_product}'>Открыть товар</a>\n"
                )

                if user_plan == "plan_pro" and qty_total:
                    msg += f"📦 <b>Остаток:</b> {qty_total} шт.\n"

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
            logger.info(f"📊 Товаров в БД: {len(products)}")
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

            # Проверяем метрики после каждого цикла
            await error_tracker.check_and_alert()

            await asyncio.sleep(poll)

        except Exception as e:
            logger.exception(f"Критическая ошибка в monitor_loop: {e}")
            await asyncio.sleep(poll)


async def cleanup_old_data(container: Container):
    """Периодическая очистка старых данных."""
    while True:
        try:
            await asyncio.sleep(86400)  # Раз в сутки
            logger.info("Запуск очистки старых данных...")
            
            # Очистка истории
            await container.db.cleanup_old_history_by_plan()
            logger.info("✅ История цен очищена")
            
            # Удаление просроченных товаров для бесплатного тарифа
            deleted = await container.db.cleanup_expired_products()
            if deleted > 0:
                logger.info(f"✅ Удалено {deleted} просроченных товаров (бесплатный тариф)")
            
            logger.info("Очистка завершена")
        except Exception as e:
            logger.exception(f"Ошибка при очистке данных: {e}")


async def auto_backup(container: Container):
    """Автоматический бэкап БД каждую ночь."""
    while True:
        try:
            # Ждём до 03:00
            now = datetime.now()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now > target:
                target += timedelta(days=1)
            
            wait_seconds = (target - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            
            logger.info("🔄 Запуск автоматического бэкапа...")
            
            # Выполняем бэкап через subprocess
            import subprocess
            result = subprocess.run(
                ["bash", "scripts/backup.sh", f"auto_{datetime.now().strftime('%Y%m%d')}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("✅ Автоматический бэкап выполнен успешно")
                # Уведомляем админа
                from aiogram import Bot
                bot = Bot(token=settings.BOT_TOKEN)
                await bot.send_message(
                    settings.ADMIN_CHAT_ID,
                    "✅ Автоматический бэкап БД выполнен успешно"
                )
            else:
                logger.error(f"❌ Ошибка бэкапа: {result.stderr}")
                
        except Exception as e:
            logger.exception(f"Ошибка при автоматическом бэкапе: {e}")


async def health_check_loop(container: Container, bot: Bot):
    """Периодическая проверка здоровья системы."""
    monitor = get_health_monitor()
    
    # Регистрируем callback для алертов
    async def send_health_alert(alert_data: Dict):
        try:
            await bot.send_message(
                settings.ADMIN_CHAT_ID,
                alert_data['message'],
                parse_mode="HTML"
            )
        except Exception as e:
            logger.exception(f"Failed to send health alert: {e}")
    
    monitor.register_alert_callback(send_health_alert)
    
    while True:
        try:
            # Проверяем каждые 5 минут
            await asyncio.sleep(300)
            
            logger.info("Выполняю проверку здоровья системы...")
            health_data = await monitor.perform_full_check(container.db)
            
            if health_data['overall_status'] != HealthStatus.HEALTHY:
                logger.warning(f"Health check: {health_data['overall_status'].value}")
            else:
                logger.info("Health check: система здорова")
                
        except Exception as e:
            logger.exception(f"Ошибка в health_check_loop: {e}")
            await asyncio.sleep(300)

async def main():
    """Основная функция запуска бота."""
    logger.info("🚀 Запуск бота...")

    # Создаём объекты
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    db = DB(str(settings.DATABASE_DSN))
    await db.connect()
    logger.info("✅ Подключение к БД установлено")

    # Создаём PriceFetcher с поддержкой x-pow
    # Управляется через переменную окружения USE_XPOW (по умолчанию True)
    fetcher = PriceFetcher(use_xpow=settings.USE_XPOW)
    if settings.USE_XPOW:
        logger.info("✅ X-POW токен включён (для получения данных о всех складах)")
    else:
        logger.info("ℹ️ X-POW токен отключён")
    container = Container(db=db, price_fetcher=fetcher)

    # Добавляем routers
    dp.include_router(start_h.router)
    dp.include_router(plan_h.router)
    dp.include_router(products_h.router)
    dp.include_router(settings_h.router)
    dp.include_router(region_h.router)
    dp.include_router(stats_h.router)
    dp.include_router(onboarding_h.router)
    dp.include_router(admin_h.router)

    dp.message.middleware(RateLimitMiddleware(rate_limit=3))
    dp.message.middleware(DependencyInjectionMiddleware(container))
    dp.callback_query.middleware(DependencyInjectionMiddleware(container))

    # Dependency injection для handlers
    dp["db"] = db
    dp["price_fetcher"] = fetcher

    # Запускаем монитор в фоне
    monitor_task = asyncio.create_task(monitor_loop(container, bot))
    logger.info("✅ Монитор цен запущен")

    # Запускаем очистку старых данных
    cleanup_task = asyncio.create_task(cleanup_old_data(container))
    logger.info("✅ Задача очистки данных запущена")

    health_task = asyncio.create_task(health_check_loop(container, bot))
    logger.info("✅ Задача проверки здоровья системы запущена")

    # Запускаем автоматический бэкап
    backup_task = asyncio.create_task(auto_backup(container))
    logger.info("✅ Задача автоматического бэкапа запущена")

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
        cleanup_task.cancel()
        backup_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        try:
            await backup_task
        except asyncio.CancelledError:
            pass
        try:
            await health_task
        except asyncio.CancelledError:
            pass

        # Закрываем XPowFetcher если используется
        try:
            from services.xpow_fetcher import close_xpow_fetcher
            await close_xpow_fetcher()
            logger.info("✅ XPowFetcher закрыт")
        except Exception as e:
            logger.warning(f"Ошибка при закрытии XPowFetcher: {e}")
        
        await fetcher.close()
        await db.close()
        await bot.session.close()
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка через Ctrl+C")
