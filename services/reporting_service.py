"""
Сервис для формирования отчётов.
"""
import logging
from typing import Dict
from aiogram import Bot
from config import settings

logger = logging.getLogger(__name__)


class ReportingService:
    """
    Сервис отчётов.

    Отвечает за формирование и отправку отчётов администратору.
    """

    def __init__(self, bot: Bot, poll_interval: int):
        self.bot = bot
        self.poll_interval = poll_interval
        self.hourly_metrics = {"processed": 0, "errors": 0, "notifications": 0}
        self.cycles_count = 0
        self.report_every = max(1, 3600 // poll_interval)

    def update_metrics(self, cycle_metrics: Dict[str, int]):
        """
        Обновить накопленные метрики.

        Args:
            cycle_metrics: Метрики текущего цикла
        """
        for key in self.hourly_metrics:
            self.hourly_metrics[key] += cycle_metrics.get(key, 0)
        
        self.cycles_count += 1
    
    def should_send_report(self) -> bool:
        """Проверить нужно ли отправлять отчёт."""
        return self.cycles_count >= self.report_every
    
    async def send_hourly_report(self):
        """Отправить почасовой отчёт администратору."""
        report = (
            "📊 <b>Отчёт за последний час</b>\n\n"
            f"✅ Обработано товаров: {self.hourly_metrics['processed']}\n"
            f"❌ Ошибок: {self.hourly_metrics['errors']}\n"
            f"🔔 Уведомлений отправлено: {self.hourly_metrics['notifications']}\n\n"
            f"⏰ Интервал проверки: {self.poll_interval} сек"
        )
        
        try:
            await self.bot.send_message(
                settings.ADMIN_CHAT_ID,
                report,
                parse_mode="HTML"
            )
            logger.info("Отчёт отправлен администратору")
            
        except Exception as e:
            logger.error(f"Не удалось отправить отчёт админу: {e}")
        
        # Сбрасываем метрики
        self.reset_metrics()
    
    def reset_metrics(self):
        """Сбросить накопленные метрики."""
        self.hourly_metrics = {"processed": 0, "errors": 0, "notifications": 0}
        self.cycles_count = 0
    
    def format_cycle_log(self, metrics: Dict[str, int]) -> str:
        """
        Форматировать лог сообщение для цикла.
        
        Args:
            metrics: Метрики цикла
        
        Returns:
            Строка для логирования
        """
        return (
            f"Цикл завершён: "
            f"обработано={metrics['processed']}, "
            f"ошибок={metrics['errors']}, "
            f"уведомлений={metrics['notifications']}"
        )
