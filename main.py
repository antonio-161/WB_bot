"""
Главный файл бота - точка входа.
"""
import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import Bot, BaseMiddleware, Dispatcher
from aiogram.types import BotCommand

from config import settings
from models import ProductRow
from services.container import Container
from services.db import DB
from services.price_fetcher import PriceFetcher
from services.monitor_service import MonitorService
from services.background_service import BackgroundService
from services.reporting_service import ReportingService
from services.xpow_fetcher import get_xpow_fetcher

# Импорт handlers
from handlers import (
    plan as plan_h,
    start as start_h,
    settings as settings_h,
    region as region_h,
    stats as stats_h,
    onboarding as onboarding_h,
    admin as admin_h,
    products as products_h,
    export as export_h
)

from utils.rate_limiter import RateLimitMiddleware
from utils.error_tracker import get_error_tracker

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DependencyInjectionMiddleware(BaseMiddleware):
    """Middleware для автоматической инъекции зависимостей в handlers."""
    
    def __init__(self, container: Container):
        super().__init__()
        self.container = container
    
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        # Инжектим репозитории
        data["user_repo"] = self.container.get_user_repo()
        data["product_repo"] = self.container.get_product_repo()
        data["price_history_repo"] = self.container.get_price_history_repo()
        
        # Инжектим бизнес-сервисы
        data["user_service"] = self.container.get_user_service()
        data["product_service"] = self.container.get_product_service()
        data["settings_service"] = self.container.get_settings_service()
        
        # Container для доступа к другим сервисам
        data["container"] = self.container
        
        return await handler(event, data)


async def monitor_loop(
    monitor_service: MonitorService,
    reporting_service: ReportingService,
    poll_interval: int
):
    """Главный цикл мониторинга цен."""
    logger.info(f"🔄 Запущен цикл мониторинга (интервал: {poll_interval}s)")

    while True:
        try:
            # ✅ ДОБАВЬ ЭТО: Прогрев перед каждым циклом
            if settings.USE_XPOW:
                try:
                    fetcher = await get_xpow_fetcher()
                    logger.info("🔥 Делаю прогрев перед циклом мониторинга...")
                    warmup_success = await fetcher.do_warmup_cycle()
                    
                    if not warmup_success:
                        logger.warning("⚠️ Прогрев не удался, продолжаю без него")
                    
                    # Небольшая пауза после прогрева
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"❌ Ошибка прогрева: {e}")

            logger.info("Начинаю цикл мониторинга...")
            
            # Получаем все товары
            product_repo = monitor_service.container.get_product_repo()
            products = await product_repo.get_all_products()
            
            logger.info(f"📊 Товаров в БД: {len(products)}")
            
            if not products:
                logger.info("Нет товаров для мониторинга")
                await asyncio.sleep(poll_interval)
                continue
            
            # Конвертируем в ProductRow
            product_rows = [ProductRow(**p) for p in products]
            
            # Обрабатываем товары пакетами
            cycle_metrics = await monitor_service.process_batch(
                product_rows,
                batch_size=50,
                delay_between_batches=1.0
            )
            
            # Логируем результаты
            logger.info(reporting_service.format_cycle_log(cycle_metrics))
            
            # Обновляем метрики
            reporting_service.update_metrics(cycle_metrics)
            
            # Отправляем отчёт если нужно
            if reporting_service.should_send_report():
                await reporting_service.send_hourly_report()
            
            # Проверяем метрики ошибок
            error_tracker = get_error_tracker()
            await error_tracker.check_and_alert()

            # ✅ Выводим статистику ПОСЛЕ цикла
            if settings.USE_XPOW:
                try:
                    fetcher = await get_xpow_fetcher()
                    stats = fetcher.get_stats()
                    logger.info(
                        f"📊 XPow stats: открытых вкладок={stats['open_pages']}, "
                        f"сессий={stats['total_sessions']}, "
                        f"запросов в текущей сессии={stats['current_session_requests']}"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить статистику: {e}")

            await asyncio.sleep(poll_interval)
            
        except Exception as e:
            logger.exception(f"Критическая ошибка в monitor_loop: {e}")
            await asyncio.sleep(poll_interval)


async def setup_bot_commands(bot: Bot):
    """Установка команд бота."""
    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(
            command="admin", description="🔧 Админ панель (только для админа)"
        ),
    ])
    logger.info("✅ Команды бота установлены")


def setup_dispatcher(dp: Dispatcher, container: Container):
    """Настройка диспетчера: подключение handlers и middleware."""
    
    # Подключаем handlers
    dp.include_router(start_h.router)
    dp.include_router(plan_h.router)
    dp.include_router(settings_h.router)
    dp.include_router(region_h.router)
    dp.include_router(stats_h.router)
    dp.include_router(onboarding_h.router)
    dp.include_router(admin_h.router)
    dp.include_router(products_h.router)
    dp.include_router(export_h.router)
    
    # Подключаем middleware
    dp.message.middleware(RateLimitMiddleware(rate_limit=3))
    dp.update.middleware(DependencyInjectionMiddleware(container))
    
    logger.info("✅ Dispatcher настроен")


async def initialize_services(bot: Bot) -> tuple:
    """Инициализация всех сервисов."""
    # Создаём подключение к БД
    db = DB(str(settings.DATABASE_DSN))
    await db.connect()
    logger.info("✅ Подключение к БД установлено")
    
    # ✅ ДОБАВЬ: Инициализация XPowFetcher ПЕРЕД PriceFetcher
    if settings.USE_XPOW:
        logger.info("🔥 Инициализирую XPowFetcher...")
        try:
            fetcher_instance = await get_xpow_fetcher()
            logger.info("✅ XPowFetcher готов")
        except Exception as e:
            logger.error(f"❌ Не удалось инициализировать XPowFetcher: {e}")
    
    # Создаём PriceFetcher
    fetcher = PriceFetcher(use_xpow=settings.USE_XPOW)
    if settings.USE_XPOW:
        logger.info("✅ PriceFetcher настроен с X-POW токеном")
    else:
        logger.info("ℹ️ PriceFetcher настроен без X-POW токена")
    
    # Создаём контейнер зависимостей
    container = Container(db=db, price_fetcher=fetcher)
    
    # Создаём сервисы
    monitor_service = MonitorService(container, bot)
    background_service = BackgroundService(container, bot)
    reporting_service = ReportingService(bot, settings.POLL_INTERVAL_SECONDS)
    
    logger.info("✅ Все сервисы инициализированы")
    
    return container, monitor_service, background_service, reporting_service


async def cleanup_services(container: Container, background_tasks: list):
    """Очистка ресурсов при завершении."""
    logger.info("🛑 Начинаю остановку сервисов...")
    
    # Отменяем фоновые задачи
    if background_tasks:
        await BackgroundService.cancel_all_tasks(background_tasks)
    
    # ← ДОБАВЬ: Закрываем все активные соединения
    if container.db.pool:
        try:
            # Завершаем все активные транзакции
            await container.db.pool.expire_connections()
            logger.info("✅ Активные соединения БД закрыты")
        except Exception as e:
            logger.warning(f"Ошибка при закрытии соединений: {e}")
    
    # Закрываем XPowFetcher
    try:
        from services.xpow_fetcher import close_xpow_fetcher
        await close_xpow_fetcher()
        logger.info("✅ XPowFetcher закрыт")
    except Exception as e:
        logger.warning(f"Ошибка при закрытии XPowFetcher: {e}")
    
    # Закрываем PriceFetcher
    await container.price_fetcher.close()
    
    # Закрываем БД
    await container.db.close()
    
    logger.info("✅ Все сервисы остановлены")


async def main():
    """Главная функция запуска бота."""
    logger.info("🚀 Запуск бота...")
    
    # Создаём бота
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    
    # ✅ ИЗМЕНИ: Инициализируем сервисы (с прогревом внутри)
    logger.info("🔧 Инициализирую сервисы...")
    container, monitor_service, background_service, reporting_service = \
        await initialize_services(bot)
    logger.info("✅ Все сервисы готовы к работе")
    
    # Настраиваем dispatcher
    setup_dispatcher(dp, container)
    
    # Устанавливаем команды
    await setup_bot_commands(bot)
    
    # Запускаем фоновые задачи
    background_tasks = background_service.start_all_tasks()
    
    # ✅ ДОБАВЬ: Логируем перед стартом монитора
    logger.info("🎯 Запускаю цикл мониторинга цен...")
    
    # Запускаем цикл мониторинга
    monitor_task = asyncio.create_task(
        monitor_loop(
            monitor_service,
            reporting_service,
            settings.POLL_INTERVAL_SECONDS
        ),
        name="monitor_loop"
    )
    logger.info("✅ Монитор цен запущен")
    
    try:
        logger.info("✅ Бот готов к работе")
        
        # Запускаем polling
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"]
        )
        
    except KeyboardInterrupt:
        logger.info("⛔ Получен сигнал остановки (Ctrl+C)")
        
    finally:
        # Отменяем монитор
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("Monitor loop cancelled")
        
        # Очищаем ресурсы
        await cleanup_services(container, background_tasks)
        
        # Закрываем сессию бота
        await bot.session.close()
        
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка через Ctrl+C")
