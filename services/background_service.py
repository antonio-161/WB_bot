"""
Сервис для фоновых задач (очистка, бэкапы, health check).
"""
import asyncio
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict

from aiogram import Bot
from services.container import Container
from utils.health_monitor import get_health_monitor
from utils.error_tracker import get_error_tracker
from config import settings

logger = logging.getLogger(__name__)


class BackgroundService:
    """
    Сервис фоновых задач.

    Отвечает за:
    - Очистку старых данных
    - Автоматические бэкапы
    - Health checks
    """

    def __init__(self, container: Container, bot: Bot):
        self.container = container
        self.bot = bot
        self.price_history_repo = container.get_price_history_repo()
        self.product_repo = container.get_product_repo()
    
    async def cleanup_old_data_loop(self):
        """Периодическая очистка старых данных (раз в сутки)."""
        while True:
            try:
                await asyncio.sleep(86400)  # 24 часа
                
                logger.info("Запуск очистки старых данных...")
                
                # Очистка истории по тарифам
                deleted = await self.price_history_repo.cleanup_by_plan()
                
                logger.info(
                    f"✅ История цен очищена: "
                    f"Free={deleted['plan_free']}, "
                    f"Basic={deleted['plan_basic']}, "
                    f"Pro={deleted['plan_pro']}"
                )
                
                logger.info("Очистка завершена")
                
            except Exception as e:
                logger.exception(f"Ошибка при очистке данных: {e}")
    
    async def auto_backup_loop(self):
        """Автоматический бэкап БД каждую ночь в 03:00."""
        while True:
            try:
                # Вычисляем время до следующего бэкапа
                now = datetime.now()
                target = now.replace(hour=3, minute=0, second=0, microsecond=0)
                
                if now > target:
                    target += timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                
                logger.info(
                    f"Следующий бэкап запланирован на "
                    f"{target.strftime('%d.%m.%Y %H:%M')}"
                )
                
                await asyncio.sleep(wait_seconds)
                
                # Выполняем бэкап
                logger.info("🔄 Запуск автоматического бэкапа...")
                
                backup_name = f"auto_{datetime.now().strftime('%Y%m%d')}"
                
                result = subprocess.run(
                    ["bash", "scripts/backup.sh", backup_name],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 минут на бэкап
                )
                
                if result.returncode == 0:
                    logger.info("✅ Автоматический бэкап выполнен успешно")
                    
                    # Уведомляем админа
                    await self.bot.send_message(
                        settings.ADMIN_CHAT_ID,
                        "✅ Автоматический бэкап БД выполнен успешно"
                    )
                else:
                    logger.error(
                        f"❌ Ошибка бэкапа: {result.stderr}"
                    )
                    
                    # Уведомляем админа об ошибке
                    await self.bot.send_message(
                        settings.ADMIN_CHAT_ID,
                        f"❌ Ошибка автоматического бэкапа:\n"
                        f"<code>{result.stderr[:500]}</code>",
                        parse_mode="HTML"
                    )
                    
            except subprocess.TimeoutExpired:
                logger.error("❌ Бэкап превысил таймаут 5 минут")
                
            except Exception as e:
                logger.exception(f"Ошибка при автоматическом бэкапе: {e}")
    
    async def health_check_loop(self):
        """Периодическая проверка здоровья системы (каждые 5 минут)."""
        monitor = get_health_monitor()
        
        # Регистрируем callback для алертов
        async def send_health_alert(alert_data: Dict):
            try:
                await self.bot.send_message(
                    settings.ADMIN_CHAT_ID,
                    alert_data['message'],
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.exception(f"Failed to send health alert: {e}")
        
        monitor.register_alert_callback(send_health_alert)
        
        while True:
            try:
                await asyncio.sleep(300)  # 5 минут
                
                logger.info("Выполняю проверку здоровья системы...")
                
                health_data = await monitor.perform_full_check(
                    self.container.db
                )
                
                status = health_data['overall_status']
                
                if status.value != "healthy":
                    logger.warning(f"Health check: {status.value}")
                else:
                    logger.info("Health check: система здорова")
                
            except Exception as e:
                logger.exception(f"Ошибка в health_check_loop: {e}")
                await asyncio.sleep(300)
    
    async def error_tracking_loop(self):
        """
        Периодическая проверка метрик ошибок API.
        Проверяет каждые 5 минут.
        """
        tracker = get_error_tracker()
        
        # Регистрируем callback для алертов
        async def send_error_alert(alert_data: Dict):
            try:
                await self.bot.send_message(
                    settings.ADMIN_CHAT_ID,
                    alert_data['message'],
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.exception(f"Failed to send error alert: {e}")
        
        tracker.register_alert_callback(send_error_alert)
        
        while True:
            try:
                await asyncio.sleep(300)  # 5 минут
                
                # Проверяем и отправляем алерты при необходимости
                await tracker.check_and_alert()
                
            except Exception as e:
                logger.exception(f"Ошибка в error_tracking_loop: {e}")
                await asyncio.sleep(300)
    
    def start_all_tasks(self) -> list[asyncio.Task]:
        """
        Запустить все фоновые задачи.
        
        Returns:
            Список Task объектов
        """
        tasks = [
            asyncio.create_task(
                self.cleanup_old_data_loop(),
                name="cleanup_data"
            ),
            asyncio.create_task(
                self.auto_backup_loop(),
                name="auto_backup"
            ),
            asyncio.create_task(
                self.health_check_loop(),
                name="health_check"
            ),
            asyncio.create_task(
                self.error_tracking_loop(),
                name="error_tracking"
            )
        ]
        
        logger.info(
            f"✅ Запущено {len(tasks)} фоновых задач: "
            f"{', '.join(t.get_name() for t in tasks)}"
        )
        
        return tasks
    
    @staticmethod
    async def cancel_all_tasks(tasks: list[asyncio.Task]):
        """Отменить все фоновые задачи."""
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"Task {task.get_name()} cancelled")
